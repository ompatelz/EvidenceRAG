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
            }
            caps = await client.call_tool("capabilities", {})
            assert caps.structuredContent is not None
            assert caps.structuredContent["generation"] == "agent_supplied_draft_only"
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
            assert (
                catalog.structuredContent["documents"][0]["document_id"] == document["document_id"]
            )
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
