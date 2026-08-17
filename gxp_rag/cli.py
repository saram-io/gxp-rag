"""Rich Command Line Interface (CLI) for GxP Document Draft Agent."""

import asyncio
from pathlib import Path
from typing import Optional
import typer
import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from gxp_rag.agent.gxp_agent import GxPDraftingService
from gxp_rag.config import settings
from gxp_rag.hitl.approval_workflow import ApprovalWorkflowManager
from gxp_rag.hitl.audit_logger import AuditLogger
from gxp_rag.models.provider_factory import ModelProviderFactory
from gxp_rag.rag.qdrant_store import QdrantStore
from gxp_rag.schemas.audit import UserRole
from gxp_rag.schemas.document import DocumentType

app = typer.Typer(
    name="gxp-rag",
    help="AI GxP Document Draft Agent with Pydantic AI, Qdrant RAG, and HITL 21 CFR Part 11 Approval.",
    add_completion=False,
)
approvals_app = typer.Typer(name="approvals", help="Manage Human-in-the-Loop review requests.")
app.add_typer(approvals_app, name="approvals")

console = Console()


@app.command("ingest")
def ingest_documents(
    path: str = typer.Argument("./sample_data", help="File or directory path of GxP documents to ingest"),
    collection: Optional[str] = typer.Option(None, help="Target Qdrant collection name"),
):
    """Ingest, parse, embed, and index GxP documents into Qdrant."""
    target_path = Path(path)
    if not target_path.exists():
        console.print(f"[bold red]Error: Path not found: {path}[/bold red]")
        raise typer.Exit(code=1)

    store = QdrantStore(collection_name=collection)
    with console.status(f"[bold green]Ingesting documents from {path} into Qdrant...[/bold green]"):
        if target_path.is_file():
            count = store.ingest_document(target_path)
            console.print(f"[bold green]✓ Ingested single file: {target_path.name} ({count} chunks)[/bold green]")
        else:
            results = store.ingest_directory(target_path)
            table = Table(title="Ingestion Summary")
            table.add_column("File Name", style="cyan")
            table.add_column("Chunks Indexed", style="green")
            for filename, count in results.items():
                table.add_row(filename, str(count))
            console.print(table)


@app.command("search")
def search_knowledge_base(
    query: str = typer.Argument(..., help="Semantic search query"),
    limit: int = typer.Option(5, "--limit", "-l", help="Max results to return"),
    doc_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by document type"),
):
    """Search Qdrant GxP knowledge base."""
    store = QdrantStore()
    doc_types = [doc_type] if doc_type else None
    results = store.search(query, limit=limit, doc_types=doc_types)

    if not results:
        console.print("[yellow]No relevant chunks found in Qdrant.[/yellow]")
        return

    table = Table(title=f"Qdrant Semantic Search Results for: '{query}'")
    table.add_column("#", style="dim", width=4)
    table.add_column("Doc ID", style="bold cyan")
    table.add_column("Title", style="white")
    table.add_column("Section", style="yellow")
    table.add_column("Score", style="green")
    table.add_column("Snippet", style="dim")

    for idx, r in enumerate(results, 1):
        snippet = (r.text.replace("\n", " ")[:100] + "...") if len(r.text) > 100 else r.text
        table.add_row(str(idx), r.doc_id, r.doc_title, r.section_heading or "General", f"{r.score:.4f}", snippet)

    console.print(table)


@app.command("draft")
def draft_document_cli(
    prompt: str = typer.Argument(..., help="Requirements/prompt for drafting"),
    doc_type: str = typer.Option("SOP", "--type", "-t", help="Document type (SOP, WORK_INSTRUCTION, etc.)"),
    department: str = typer.Option("Quality Assurance", "--dept", "-d", help="Originating department"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model (e.g., openai:gpt-4o, anthropic:claude-3-7-sonnet-latest, test)"),
    out: Optional[str] = typer.Option(None, "--out", "-o", help="Output markdown filepath"),
    request_approval: bool = typer.Option(False, "--approval", help="Automatically submit for Human Approval"),
):
    """Draft a compliant GxP document using Pydantic AI agent and Qdrant RAG."""
    async def _run():
        service = GxPDraftingService(default_model=model)
        dtype = DocumentType(doc_type) if doc_type in DocumentType.__members__ else DocumentType.SOP

        with console.status("[bold green]Pydantic AI Agent is retrieving context and drafting GxP document...[/bold green]"):
            draft = await service.draft_document(
                prompt=prompt,
                doc_type=dtype,
                department=department,
                model_spec=model,
                auto_request_approval=request_approval,
            )
            compliance = service.evaluate_compliance(draft)

        console.print(Panel.fit(
            f"[bold green]GxP Document Generated Successfully![/bold green]\n"
            f"[cyan]Doc ID:[/cyan] {draft.doc_id}\n"
            f"[cyan]Title:[/cyan] {draft.title}\n"
            f"[cyan]Type:[/cyan] {draft.doc_type.value}\n"
            f"[cyan]ALCOA+ Compliance Score:[/cyan] {compliance.compliance_score:.1f}%\n"
            f"[cyan]Grounded Citations:[/cyan] {len(draft.citations)} sources from Qdrant",
            title="Draft Summary"
        ))

        md_content = draft.to_markdown()
        if out:
            out_path = Path(out)
            out_path.write_text(md_content, encoding="utf-8")
            console.print(f"[bold green]✓ Saved draft to {out}[/bold green]")
        else:
            console.print(Panel(md_content, title=f"Markdown Preview: {draft.doc_id}", expand=False))

    asyncio.run(_run())


@approvals_app.command("list")
def list_approvals_cli():
    """List pending and reviewed Human-in-the-Loop approval requests."""
    manager = ApprovalWorkflowManager()
    approvals = manager.list_approvals()

    if not approvals:
        console.print("[yellow]No approval requests found.[/yellow]")
        return

    table = Table(title="Human-in-the-Loop Approvals (21 CFR Part 11)")
    table.add_column("Request ID", style="bold cyan")
    table.add_column("Doc ID", style="white")
    table.add_column("Title", style="white")
    table.add_column("Status", style="yellow")
    table.add_column("Created At", style="dim")
    table.add_column("Signatures", style="green")

    for a in approvals:
        status_style = "green" if a.status.value == "APPROVED" else "yellow" if a.status.value == "PENDING" else "red"
        sigs = f"{len(a.signatures)} e-sigs" if a.signatures else "None"
        table.add_row(
            a.request_id,
            a.doc_id,
            a.doc_title,
            f"[{status_style}]{a.status.value}[/{status_style}]",
            a.created_at[:19],
            sigs,
        )

    console.print(table)


@approvals_app.command("sign")
def sign_approval_cli(
    request_id: str = typer.Argument(..., help="Approval Request ID"),
    signer_name: str = typer.Option(..., "--name", "-n", help="Full printed name of signer"),
    user_id: str = typer.Option("qa_lead_01", "--user", "-u", help="User ID"),
    role: str = typer.Option("QA_SPECIALIST", "--role", "-r", help="Role (QA_SPECIALIST, QA_MANAGER, SME_REVIEWER)"),
    comments: str = typer.Option("Approved following technical review", "--comments", "-c", help="Review comments"),
):
    """Sign and approve a pending draft with 21 CFR Part 11 Electronic Signature."""
    manager = ApprovalWorkflowManager()
    user_role = UserRole(role) if role in UserRole.__members__ else UserRole.QA_SPECIALIST

    with console.status(f"[bold green]Signing and approving request {request_id}...[/bold green]"):
        appr = manager.approve(
            request_id=request_id,
            signer_name=signer_name,
            user_id=user_id,
            signer_role=user_role,
            comments=comments,
        )
        sig = appr.signatures[-1] if appr.signatures else None

    console.print(Panel.fit(
        f"[bold green]✓ 21 CFR Part 11 Electronic Signature Executed![/bold green]\n"
        f"[cyan]Request ID:[/cyan] {appr.request_id}\n"
        f"[cyan]Signer:[/cyan] {sig.signer_name if sig else signer_name} ({sig.signer_role if sig else role})\n"
        f"[cyan]Timestamp:[/cyan] {sig.timestamp if sig else ''}\n"
        f"[cyan]SHA-256 Signature Digest:[/cyan] {sig.signature_digest if sig else ''}",
        title="Electronic Signature Record"
    ))


@app.command("audit-verify")
def verify_audit_trail_cli():
    """Verify cryptographic SHA-256 chain integrity of the 21 CFR Part 11 audit log."""
    logger = AuditLogger()
    result = logger.verify_integrity()

    if result.get("valid"):
        console.print(Panel.fit(
            f"[bold green]✓ Audit Trail Integrity Verified (Pass)![/bold green]\n"
            f"[cyan]Total Records:[/cyan] {result.get('total_records')}\n"
            f"[cyan]Latest SHA-256 Hash:[/cyan] {result.get('latest_hash')}\n"
            f"[green]All records are sequentially linked and cryptographically untampered.[/green]",
            title="21 CFR Part 11 Audit Integrity"
        ))
    else:
        console.print(Panel.fit(
            f"[bold red]✗ Audit Trail Verification FAILED![/bold red]\n"
            f"[red]Error:[/red] {result.get('error')}",
            title="Integrity Failure"
        ))


@app.command("serve")
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Bind host"),
    port: int = typer.Option(8000, "--port", "-p", help="Bind port"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload"),
):
    """Start the FastAPI web server."""
    console.print(f"[bold green]Starting GxP Document Draft Agent Web App at http://{host}:{port}[/bold green]")
    uvicorn.run("gxp_rag.web.app.app" if reload else "gxp_rag.web.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
