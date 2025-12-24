import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from config.config_manager import Configuration, load_config
from models.table_access_info import TableAccessInfo
from modifier.code_modifier import CodeModifier

# Add src to sys.path
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root / "src"))

# Load .env
load_dotenv(project_root / ".env")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("run_modification_context_generator")


def main():
    parser = argparse.ArgumentParser(
        description="Debug CodeModifier.generate_modification_plans."
    )
    # file_path argument removed as per user request
    parser.add_argument(
        "--config", type=str, default="config.json", help="Path to config.json"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Force use of mock LLM provider"
    )

    args = parser.parse_args()
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        if (project_root / args.config).exists():
            config_path = project_root / args.config
        else:
            logger.error(f"Config file not found: {config_path}")
            return

    # Load Config
    try:
        config: Configuration = load_config(str(config_path))
        if args.mock:
            config.llm_provider = "mock"
            logger.info("Forcing LLM Provider to 'mock'")

        logger.info(f"Loaded config from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return

    # Initialize CodeModifier
    try:
        # Instantiate CodeModifier with project_root (ApplyCrypto) for context generation scope
        code_modifier = CodeModifier(config=config)
        logger.info("Initialized CodeModifier")
    except Exception as e:
        logger.error(f"Failed to initialize CodeModifier: {e}")
        return

    # Construct TableAccessInfo
    if not config.access_tables:
        logger.error("No access_tables found in config.json")
        return

    first_table = config.access_tables[0]
    target_table_name = first_table.table_name

    # Handle column format
    target_columns = []
    for col in first_table.columns:
        if isinstance(col, str):
            target_columns.append({"name": col, "new_column": False})
        elif hasattr(col, "dict"):
            target_columns.append(col.dict())
        elif isinstance(col, dict):
            target_columns.append(col)
        else:
            target_columns.append({"name": str(col), "new_column": False})

    # Prepare file list - Scan target_project
    target_files = []
    target_project_path = Path(config.target_project)

    if not target_project_path.exists():
        logger.error(f"Target project path does not exist: {target_project_path}")
        return

    logger.info(f"Scanning target project: {target_project_path}")

    extensions = (
        config.source_file_types if config.source_file_types else [".java", ".xml"]
    )

    for ext in extensions:
        # Check for both .ext and *.ext formats just in case
        pattern = f"*{ext}" if not ext.startswith("*") else ext
        if not pattern.startswith("*.") and pattern.startswith("."):
            pattern = "*" + pattern

        # Simple recursive search
        target_files.extend(
            [str(f.resolve()) for f in target_project_path.rglob(pattern)]
        )

    if not target_files:
        logger.warning(
            f"No source files found in {target_project_path} with extensions {extensions}"
        )
        return

    # We assume 'service' layer for simplicity in this debug script,
    # effectively forcing the modification context generator to see these files as service layer files.
    layer_files = {"service": target_files}

    table_info = TableAccessInfo(
        table_name=target_table_name,
        columns=target_columns,
        access_files=target_files,
        query_type="SELECT",
        layer="service",
        layer_files=layer_files,
    )

    logger.info(
        f"Generating ModificationContexts (batches) for table '{target_table_name}' using files: {len(target_files)} files found."
    )

    # Generate Contexts (Batches)
    try:
        from dataclasses import asdict

        # Access the generator directly from CodeModifier
        context_generator = code_modifier.modification_context_generator

        batches = context_generator.generate(table_info)

        print("\n" + "=" * 50)
        print(f"Generated {len(batches)} Batches (ModificationContexts)")
        print("=" * 50)

        serialized_batches = []

        for i, batch in enumerate(batches):
            print(f"\n[Batch {i + 1}]")
            print(f"  Layer: {batch.layer}")
            print(f"  File Count: {batch.file_count}")
            print("  Files:")
            for snippet in batch.code_snippets:
                print(f"    - {snippet.path} (Length: {len(snippet.content)})")

            serialized_batches.append(asdict(batch))

        # Save to file (using config.target_project from config.json)
        target_project_path = Path(config.target_project)
        output_file = (
            target_project_path / ".applycrypto" / "modification_context_result.json"
        )

        # Ensure directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(serialized_batches, f, indent=2, default=str, ensure_ascii=False)

        print("\n" + "=" * 50)
        print(f"Result saved to: {output_file}")
        print("=" * 50)

    except Exception as e:
        logger.error(f"Context generation failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
