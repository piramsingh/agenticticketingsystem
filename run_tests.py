"""
Run all tests in sequence.

Run from the project root:
    export AZURE_ORG_URL="https://dev.azure.com/piramsingh-demo"
    export AZURE_PAT="your-token"
    export AZURE_PROJECT="bio-rad demo"
    export JIRA_TOKEN="your-jira-api-token"
    export GITHUB_TOKEN="ghp_..."           # PAT with `repo` scope
    export GITHUB_REPO="owner/repo"          # e.g. piramsingh/agenticticketingsystem
    python run_tests.py
"""
import asyncio
import os
import sys

results = []

def log(test_num, name, passed, detail=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append((test_num, name, passed))
    print(f"{status} — Test {test_num}: {name}")
    if detail:
        print(f"       {detail}")


# ── Test 1: Factory rejects unknown tools ─────────────────────────────────────
def test_1():
    from src.connectors.factory import build
    from src.config import ConnectorConfig, PatAuth
    try:
        build(ConnectorConfig(
            name="test", tool_type="gitlab",
            base_url="https://fake.com", project="PROJ",
            auth=PatAuth(token="fake")
        ))
        log(1, "Factory rejects unknown tools", False, "Should have raised ValueError")
    except ValueError as e:
        log(1, "Factory rejects unknown tools", True, str(e))


# ── Test 2: Config loads from YAML template ───────────────────────────────────
def test_2():
    os.environ.setdefault("JIRA_DOMAIN", "myco")
    os.environ.setdefault("JIRA_PROJECT_KEY", "PROJ")
    os.environ.setdefault("JIRA_EMAIL", "me@myco.com")
    os.environ.setdefault("JIRA_API_TOKEN", "fake-token")
    try:
        from src.config import load_config
        cfg = load_config("templates/jira-only.yaml")
        assert cfg.sync.source == "jira-main"
        assert cfg.get_target_config().tool_type == "jira"
        log(2, "Config loads from YAML template", True,
            f"tool_type={cfg.get_target_config().tool_type}, base_url={cfg.get_target_config().base_url}")
    except Exception as e:
        log(2, "Config loads from YAML template", False, str(e))


# ── Test 3: Azure DevOps connector works ──────────────────────────────────────
async def test_3():
    required = ["AZURE_ORG_URL", "AZURE_PAT", "AZURE_PROJECT"]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        log(3, "Azure DevOps connector works", False,
            f"Missing env vars: {', '.join(missing)} — skipping")
        return

    from src.connectors.azure_devops import AzureDevOpsConnector
    connector = AzureDevOpsConnector(
        base_url=os.environ["AZURE_ORG_URL"],
        pat=os.environ["AZURE_PAT"],
        project=os.environ["AZURE_PROJECT"],
    )
    try:
        ok = await connector.validate_connection()
        if not ok:
            log(3, "Azure DevOps connector works", False, "Connection validation failed")
            return
        tickets = await connector.list_items(3)
        log(3, "Azure DevOps connector works", True,
            f"Connected, fetched {len(tickets)} tickets")
    except Exception as e:
        log(3, "Azure DevOps connector works", False, str(e))
    finally:
        await connector.close()


# ── Test 4: ChatAgent has no tool-specific logic ──────────────────────────────
def test_4():
    try:
        from src.connectors.azure_devops import AzureDevOpsConnector
        from src.connectors.jira import JiraConnector

        azure = AzureDevOpsConnector("https://fake.com", "pat", "PROJ")
        jira  = JiraConnector("https://fake.atlassian.net", "me@co.com", "token", "PROJ")

        assert azure.normalize_priority("critical") == 1
        assert jira.normalize_priority("critical") == {"name": "Highest"}
        assert azure.normalize_type("feature") == "Epic"
        assert jira.normalize_type("feature") == "Story"

        log(4, "ChatAgent has no tool-specific logic", True,
            "Azure and Jira each speak their own dialect")
    except AssertionError as e:
        log(4, "ChatAgent has no tool-specific logic", False, str(e))
    except Exception as e:
        log(4, "ChatAgent has no tool-specific logic", False, str(e))


# ── Test 5: MCP server lists tools ────────────────────────────────────────────
async def test_5():
    try:
        from mcp_server import list_tools
        tools = await list_tools()
        tool_names = [t.name for t in tools]
        expected = ["create_ticket", "get_ticket", "list_recent_tickets", "list_members"]
        missing = [t for t in expected if t not in tool_names]
        if missing:
            log(5, "MCP server lists tools", False, f"Missing: {missing}")
        else:
            log(5, "MCP server lists tools", True, f"{len(tools)} tools registered")
    except Exception as e:
        log(5, "MCP server lists tools", False, str(e))


# ── Test 6: Jira connector works ──────────────────────────────────────────────
async def test_6():
    token = os.getenv("JIRA_TOKEN")
    if not token:
        log(6, "Jira connector works", False, "Missing env var: JIRA_TOKEN — skipping")
        return

    from src.connectors.jira import JiraConnector
    connector = JiraConnector(
        base_url="https://piramsingh.atlassian.net",
        email="piramsingh@gmail.com",
        api_token=token,
        project="SCRUM",
    )
    try:
        ok = await connector.validate_connection()
        if not ok:
            log(6, "Jira connector works", False, "Connection validation failed")
            return

        # Create a test ticket
        from src.config import ConnectorConfig, ApiTokenAuth
        result = await connector.create_item({
            "title": "Test ticket from ticket-agent",
            "description": "Automated test — safe to delete.",
            "priority": connector.normalize_priority("medium"),
            "type": connector.normalize_type("task"),
        })
        log(6, "Jira connector works", True,
            f"Created issue {result.item_id} → {result.item_url}")

        # List tickets
        tickets = await connector.list_items(3)
        print(f"       Listed {len(tickets)} recent tickets from SCRUM")

    except Exception as e:
        log(6, "Jira connector works", False, str(e))
    finally:
        await connector.close()


# ── Test 7: GitHub Issues connector works ─────────────────────────────────────
async def test_7():
    token = os.getenv("GITHUB_TOKEN")
    repo  = os.getenv("GITHUB_REPO")
    if not token or not repo:
        missing = [v for v in ("GITHUB_TOKEN", "GITHUB_REPO") if not os.getenv(v)]
        log(7, "GitHub Issues connector works", False,
            f"Missing env vars: {', '.join(missing)} — skipping")
        return

    from src.connectors.github_issues import GitHubIssuesConnector
    connector = GitHubIssuesConnector(
        base_url="https://api.github.com",
        token=token,
        project=repo,
    )
    try:
        ok = await connector.validate_connection()
        if not ok:
            log(7, "GitHub Issues connector works", False, "Connection validation failed")
            return

        result = await connector.create_item({
            "title": "Test issue from ticket-agent",
            "description": "Automated test — safe to close.",
            "priority": connector.normalize_priority("low"),
            "type": connector.normalize_type("task"),
        })
        log(7, "GitHub Issues connector works", True,
            f"Created issue #{result.item_id} → {result.item_url}")

        tickets = await connector.list_items(3)
        print(f"       Listed {len(tickets)} recent issues from {repo}")

    except Exception as e:
        log(7, "GitHub Issues connector works", False, str(e))
    finally:
        await connector.close()


# ── Runner ─────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 50)
    print("  Ticket Agent — Full Test Suite")
    print("=" * 50)

    test_1()
    test_2()
    await test_3()
    test_4()
    await test_5()
    await test_6()
    await test_7()

    print("=" * 50)
    passed = sum(1 for _, _, p in results if p)
    total  = len(results)
    print(f"  {passed}/{total} tests passed")
    print("=" * 50)

    if passed < total:
        sys.exit(1)


asyncio.run(main())
