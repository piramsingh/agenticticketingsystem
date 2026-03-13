"""
Interactive chat demo for AI-powered ticket creation

This demo shows how users can create tickets using natural language.

Run with: python demo/chat_demo.py
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent.ticket_parser import TicketParser
from src.agent.chat_agent import ChatAgent
from demo.mock_azure_connector import MockAzureDevOpsConnector
from demo.mock_jama_client import MockJamaClient
from src.config import load_config


def print_banner():
    """Print welcome banner"""
    print("\n" + "="*70)
    print("🤖 AI-POWERED TICKET CREATION AGENT")
    print("="*70)
    print("Create tickets using natural language!")
    print("Type 'help' for examples, 'quit' to exit")
    print("="*70 + "\n")


async def run_interactive_demo():
    """Run interactive chat demo"""
    print_banner()
    
    # Load config and initialize components
    config = load_config("demo/demo_config.yaml")
    
    # Create mock clients
    connector = MockAzureDevOpsConnector(config.target_tool)
    jama_client = MockJamaClient(config.jama)
    
    # Create parser and agent
    parser = TicketParser()
    agent = ChatAgent(
        parser=parser,
        connector=connector,
        jama_client=jama_client,
        project_id=config.jama.project_id
    )
    
    print("Agent initialized! Ready to create tickets.\n")
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\n👋 Goodbye!\n")
                break
            
            if user_input.lower() in ['help', 'h', '?']:
                print(agent.get_help_message())
                continue
            
            # Process the message
            print("\n🤖 Processing...\n")
            result = await agent.process_message(user_input)
            
            if result["success"]:
                print(result["message"])
                print("\n" + "-"*70)
                print("📊 Details:")
                print(f"   Title: {result['parsed']['title']}")
                print(f"   Assignee: {result['parsed']['assignee'] or 'Unassigned'}")
                print(f"   Priority: {result['parsed']['priority']}")
                print(f"   Type: {result['parsed']['type']}")
                if result['parsed']['labels']:
                    print(f"   Labels: {', '.join(result['parsed']['labels'])}")
                print("-"*70 + "\n")
            else:
                print(f"❌ Error: {result['message']}\n")
        
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!\n")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}\n")


async def run_example_scenarios():
    """Run pre-defined example scenarios"""
    print("\n" + "="*70)
    print("🎬 RUNNING EXAMPLE SCENARIOS")
    print("="*70)
    print("Watch the AI agent create tickets from natural language!\n")
    
    # Load config and initialize components
    config = load_config("demo/demo_config.yaml")
    connector = MockAzureDevOpsConnector(config.target_tool)
    jama_client = MockJamaClient(config.jama)
    parser = TicketParser()
    agent = ChatAgent(
        parser=parser,
        connector=connector,
        jama_client=jama_client,
        project_id=config.jama.project_id
    )
    
    # Example scenarios
    scenarios = [
        "Create a ticket for Jamie to fix the security issue in the backend",
        "Write a high priority bug for the login problem",
        "Add a feature request for dark mode assigned to Sarah",
        "Make a critical task to update the database schema #database #backend",
        "Create a user story for implementing the new dashboard"
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"\n{'='*70}")
        print(f"Scenario {i}/{len(scenarios)}")
        print(f"{'='*70}")
        print(f"User: {scenario}\n")
        
        result = await agent.process_message(scenario)
        
        if result["success"]:
            print(result["message"])
        else:
            print(f"❌ Error: {result['message']}")
        
        await asyncio.sleep(1)  # Pause between scenarios
    
    print(f"\n{'='*70}")
    print("✅ ALL SCENARIOS COMPLETE!")
    print(f"{'='*70}")
    print(f"\nCreated {len(scenarios)} tickets with natural language!")
    print("Each ticket was automatically synced to Jama Connect.\n")


async def main():
    """Main entry point"""
    print("\n" + "="*70)
    print("AI TICKET CREATION DEMO")
    print("="*70)
    print("\nChoose a mode:")
    print("  1. Interactive chat (type your own commands)")
    print("  2. Example scenarios (watch pre-defined examples)")
    print("  3. Both (examples first, then interactive)")
    print("="*70)
    
    choice = input("\nYour choice (1/2/3): ").strip()
    
    if choice == "1":
        await run_interactive_demo()
    elif choice == "2":
        await run_example_scenarios()
    elif choice == "3":
        await run_example_scenarios()
        print("\n" + "="*70)
        print("Now try it yourself!")
        print("="*70)
        await run_interactive_demo()
    else:
        print("\nInvalid choice. Running interactive mode...\n")
        await run_interactive_demo()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!\n")
