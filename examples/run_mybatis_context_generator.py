import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to python path to allow imports
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root / "src"))

from modifier.context_generator.mybatis_context_generator import MybatisContextGenerator
from models.table_access_info import TableAccessInfo
from models.modification_context import CodeSnippet

def run_test():
    # 1. Setup Mock Config and CodeGenerator
    mock_config = MagicMock()
    mock_config.target_project = "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung"
    mock_config.max_tokens_per_batch = 10000

    mock_code_generator = MagicMock()
    # Mock token calculation to return small number so we don't trigger splitting usually
    mock_code_generator.calculate_token_size.return_value = 100 
    mock_code_generator.create_prompt.return_value = "Prompt"

    # 2. Setup Example Data
    layer_files = {
      "service": [
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\service\\CocoonAcctAthntServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\service\\CocoonAcctDpstServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\service\\CocoonAcctWdrServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\service\\CocoonArsAthntServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\api\\common\\point\\PntCommService.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\service\\PntCustomersBankInfoService.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\service\\PntCustomersBankInfoServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\service\\PntCustomersCreateServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\issue\\service\\PntIssueChargeServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\pg\\service\\PgArsServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\pg\\service\\PgAuthServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\service\\PntUseCreditServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\service\\PntUseDirectServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\service\\PntUseHealServiceImpl.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Web_samsung\\src\\main\\java\\com\\cps\\web\\point\\custaccn\\service\\PointCustAccnService.java"
      ],
      "controller": [
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\controller\\PntCustomersBankInfoController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\controller\\PntCustomersCreateController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\issue\\controller\\PntIssueChargeController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\pg\\controller\\PgArsController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\pg\\controller\\PgAuthController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\controller\\PntUseCreditController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\controller\\PntUseDirectController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\use\\controller\\PntUseHealController.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Web_samsung\\src\\main\\java\\com\\cps\\web\\point\\custaccn\\controller\\PointCustAccnController.java"
      ],
      "repository": [
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\dao\\CocoonAcctAthntDao.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\dao\\CocoonAcctDpstDao.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\dao\\CocoonAcctWdrDao.java",
        "D:\\PII-EncryptEx\\PrimusCPS_Eai_samsung\\src\\main\\java\\com\\cps\\eai\\cocoon\\dao\\CocoonCommonDao.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\dao\\PntCustomersBankInfoDao.java",
        "D:\\PII-EncryptEx\\PrimusCPS_ExternalApi_samsung\\src\\main\\java\\com\\cps\\api\\point\\customers\\dao\\PntCustomersCreateDao.java"
      ]
    }

    table_access_info = TableAccessInfo(
        table_name="TEST_TABLE",
        columns=[{"name": "COL1", "new_column": False}],
        access_files=[],
        query_type="SELECT",
        layer_files=layer_files
    )

    # 3. Instantiate Generator
    generator = MybatisContextGenerator(mock_config, mock_code_generator)

    # 4. Mock _read_files to avoid actual file I/O
    # We want to return CodeSnippets with the path so we can verify grouping
    def mock_read_files(file_paths, project_root):
        snippets = []
        for p in file_paths:
            snippets.append(CodeSnippet(path=p, content=f"Content of {p}"))
        return snippets
    
    with patch.object(generator, '_read_files', side_effect=mock_read_files):
        # 5. Run Generate
        contexts = generator.generate(table_access_info)

    # 6. Verify Results
    print(f"Generated {len(contexts)} contexts.\n")
    
    for ctx in contexts:
        print(f"Context Layer (Group): {ctx.layer}")
        print(f"File Count: {ctx.file_count}")
        for snippet in ctx.code_snippets:
            print(f" - {snippet.path.split(chr(92))[-1]}") # Print filename (split by backslash)
        print("-" * 30)

    # Specific Assertion
    # Check 'PntCustomersBankInfo' group
    pnt_bank_group = next((c for c in contexts if c.layer == "PntCustomersBankInfo"), None)
    if pnt_bank_group:
        print("\nPASSED: Found group 'PntCustomersBankInfo'")
        files = [s.path.split(chr(92))[-1] for s in pnt_bank_group.code_snippets]
        assert "PntCustomersBankInfoService.java" in files
        assert "PntCustomersBankInfoServiceImpl.java" in files
        assert "PntCustomersBankInfoController.java" in files
        assert "PntCustomersBankInfoDao.java" in files
        print("PASSED: Group contains correct files.")
    else:
        print("\nFAILED: Group 'PntCustomersBankInfo' not found.")

if __name__ == "__main__":
    run_test()
