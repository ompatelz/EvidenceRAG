"""Real MCP client/server protocol tests with deterministic development fixtures."""

import asyncio
from pathlib import Path

import pytest

pytest.importorskip(
    "mcp", reason="Install integrations/mcp/requirements.txt for MCP protocol tests"
)

from mcp.shared.memory import create_connected_server_and_client_session

from evidence_rag.mcp_server import create_server
from evidence_rag.sdk import EvidenceRAG


def test_registered_tool_functions_without_transport(tmp_path: Path) -> None:
    """Check real tool registration and responses independently of transport sockets."""
    server = create_server(EvidenceRAG(tmp_path / "artifacts"), Path("datasets/fixtures"))
    ingest = server._tool_manager.get_tool("ingest_pdf")
    search = server._tool_manager.get_tool("search_evidence")
    assert ingest is not None and search is not None
    assert "relative_path" in ingest.parameters["properties"]
    assert ingest.fn(relative_path="../outside.pdf") == {"error": "invalid_request_or_artifact"}
    ingested = ingest.fn(relative_path="atlas-narrative.pdf")
    assert ingested["state"] == "ready"
    result = search.fn(
        document_id=ingested["document_id"],
        document_sha256=ingested["document_sha256"],
        question="calibration sampling",
    )
    assert result["pack"]["items"]
    assert result["content_trust"] == "untrusted_document_data"
    context = server._tool_manager.get_tool("fetch_connected_evidence")
    collection = server._tool_manager.get_tool("search_collection")
    assert context is not None and collection is not None
    connected = context.fn(
        document_id=ingested["document_id"],
        document_sha256=ingested["document_sha256"],
        evidence_id=result["pack"]["items"][0]["evidence_id"],
    )
    assert connected["pack"]["items"]
    assert "request" in collection.parameters["properties"]


def test_protocol_discovery_ingestion_search_and_errors(tmp_path: Path) -> None:
    async def scenario() -> None:
        engine = EvidenceRAG(tmp_path / "artifacts")
        server = create_server(engine, Path("datasets/fixtures"))
        async with create_connected_server_and_client_session(server) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools.tools} == {
                "capabilities",
                "ingest_pdf",
                "search_evidence",
                "fetch_evidence",
                "check_draft",
                "list_documents",
                "document_status",
                "fetch_page_evidence",
                "calculate_evidence",
                "doctor",
                "search_collection",
                "check_collection",
                "fetch_connected_evidence",
                "explain_check",
                "calculate_recipe",
                "fetch_visual_page",
            }
            caps = await client.call_tool("capabilities", {})
            assert caps.structuredContent is not None
            assert caps.structuredContent["generation"] == "agent_supplied_draft_only"
            assert caps.structuredContent["arithmetic_proves_narrative_claims"] is False
            loan = await client.call_tool("ingest_pdf", {"relative_path": "library-loans.pdf"})
            assert loan.structuredContent is not None
            loan_ref = {
                key: loan.structuredContent[key] for key in ("document_id", "document_sha256")
            }
            sources = await client.call_tool(
                "search_evidence", {**loan_ref, "question": "Resident renewal loan period"}
            )
            assert sources.structuredContent is not None
            items = sources.structuredContent["pack"]["items"]
            table = next(item for item in items if "| Resident |" in item["text"])
            renewal = next(item for item in items if item["text"].startswith("A renewal adds"))
            computed = await client.call_tool(
                "calculate_evidence",
                {
                    **loan_ref,
                    "calculation": {
                        "operation": "add",
                        "expected_value": "35",
                        "operands": [
                            {
                                "kind": "table_cell",
                                "evidence_id": table["evidence_id"],
                                "row": "Resident",
                                "column": "Loan period",
                            },
                            {"kind": "text", "evidence_id": renewal["evidence_id"], "unit": "days"},
                        ],
                    },
                },
            )
            assert computed.structuredContent is not None
            assert computed.structuredContent["calculation"]["result"] == "35"
            assert computed.structuredContent["calculation"]["claim_support"] == "not_assessed"
            bad = await client.call_tool("ingest_pdf", {"relative_path": "../secrets.pdf"})
            assert bad.structuredContent == {"error": "invalid_request_or_artifact"}
            ingested = await client.call_tool(
                "ingest_pdf", {"relative_path": "atlas-narrative.pdf"}
            )
            assert ingested.structuredContent is not None
            document = {
                key: ingested.structuredContent[key] for key in ("document_id", "document_sha256")
            }
            catalog = await client.call_tool("list_documents", {})
            assert catalog.structuredContent is not None
            assert {item["document_id"] for item in catalog.structuredContent["documents"]} == {
                document["document_id"],
                loan_ref["document_id"],
            }
            page = await client.call_tool(
                "fetch_page_evidence",
                {
                    **document,
                    "page_index": 0,
                    "limit": 1,
                },
            )
            assert page.structuredContent is not None
            assert len(page.structuredContent["pack"]["items"]) == 1
            result = await client.call_tool(
                "search_evidence", {**document, "question": "calibration sampling"}
            )
            assert result.structuredContent is not None
            item = result.structuredContent["pack"]["items"][0]
            assert result.structuredContent["content_trust"] == "untrusted_document_data"
            connected = await client.call_tool(
                "fetch_connected_evidence",
                {
                    **document,
                    "evidence_id": item["evidence_id"],
                },
            )
            assert connected.structuredContent is not None
            assert (
                connected.structuredContent["pack"]["items"][0]["evidence_id"]
                == item["evidence_id"]
            )
            collection = await client.call_tool(
                "search_collection",
                {
                    "request": {
                        "documents": [document, loan_ref],
                        "question": "calibration Resident",
                    }
                },
            )
            assert collection.structuredContent is not None
            assert collection.structuredContent["pack"]["items"]
            source = await client.call_tool(
                "fetch_evidence", {**document, "evidence_id": item["evidence_id"]}
            )
            assert source.structuredContent is not None
            assert source.structuredContent["anchor"]["evidence_id"] == item["evidence_id"]
            claim = "The Atlas sensor's calibration sampling rate is 20 hertz."
            checked = await client.call_tool(
                "check_draft",
                {
                    **document,
                    "question": "calibration sampling",
                    "evidence_ids": [item["evidence_id"]],
                    "draft": {
                        "status": "answered",
                        "answer": claim,
                        "claims": [
                            {
                                "text": claim,
                                "citations": [
                                    {
                                        key: item[key]
                                        for key in (
                                            "document_id",
                                            "document_version",
                                            "evidence_id",
                                            "page_index",
                                        )
                                    }
                                ],
                            }
                        ],
                    },
                },
            )
            assert checked.structuredContent is not None
            assert checked.structuredContent["reason"] == "verifier_unavailable"

    asyncio.run(scenario())
