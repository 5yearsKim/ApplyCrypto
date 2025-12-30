import logging
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock

# Add src to path
current_dir = Path(__file__).parent
src_dir = current_dir.parent / "src"
sys.path.append(str(src_dir))

from config.config_manager import Configuration
from models.table_access_info import TableAccessInfo
from modifier.code_generator.base_code_generator import BaseCodeGenerator

from modifier.context_generator.jdbc_context_generator import JdbcContextGenerator

# Setup basic logging
logging.basicConfig(level=logging.INFO)

def test_jdbc_context_generator():
    print("Starting JDBC Context Generator Test...")

    # 1. Mock Configuration
    mock_config = MagicMock(spec=Configuration)
    mock_config.target_project = "D:/RES/workspace/gam-pjt"  # Dummy project root
    mock_config.max_tokens_per_batch = 10000

    # 2. Mock BaseCodeGenerator
    mock_code_generator = MagicMock(spec=BaseCodeGenerator)
    mock_code_generator.calculate_token_size.return_value = 10
    mock_code_generator.create_prompt.return_value = "Prompt"

    # 3. Create Generator Instance
    generator = JdbcContextGenerator(mock_config, mock_code_generator)

    # 4. Prepare Mock TableAccessInfo with USER DATA
    layer_files = {
      "Repository": [
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bc\\comm\\dao\\dem\\dvo\\TGAH00017DVO.java"
      ],
      "dem_daq": [
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bc\\comm\\dao\\dem\\TGAH00017DEM.java"
      ],
      "biz": [
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bc\\comm\\biz\\BCGaPesnInfoInqrBIZ.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mng\\biz\\BZMngSalesMngBIZ.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mnger\\biz\\BZMngerInvwBIZ.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\biz\\TGTrgtBrncBIZ.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\biz\\TGTrgtFpBIZ.java"
      ],
      "svc": [
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bc\\comm\\svc\\IBCGaPesnInqrSVC.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bc\\comm\\svc\\impl\\IBCGaPesnInqrSVCImpl.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mng\\svc\\IBZMngSalesMngSVC.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mng\\svc\\impl\\IBZMngSalesMngSVCImpl.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mnger\\svc\\IBZMngerInvwSVC.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\bz\\mnger\\svc\\impl\\IBZMngerInvwSVCImpl.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\svc\\ITGTrgtBrncSVC.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\svc\\ITGTrgtFpSVC.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\svc\\impl\\ITGTrgtBrncSVCImpl.java",
        "D:\\RES\\workspace\\gam-pjt\\src\\main\\java\\sli\\gam\\tgt\\svc\\impl\\ITGTrgtFpSVCImpl.java"
      ]
    }

    table_access_info = TableAccessInfo(
        table_name="TEST_TABLE",
        columns=[],
        access_files=[],
        query_type="SELECT",
        layer_files=layer_files
    )

    # 5. Mock file reading
    generator._read_files = MagicMock(side_effect=lambda file_paths, root: [MagicMock(path=p, content=f"Content of {Path(p).name}") for p in file_paths])

    # 6. Run Generate
    contexts = generator.generate(table_access_info)

    # 7. Assertions
    print(f"Generated {len(contexts)} contexts.")
    
    # Expected groupings:
    # Repository: 1 file
    # dem_daq: 1 file
    # comm: 3 files (1 biz, 2 svc)
    # mng: 3 files (1 biz, 2 svc)
    # mnger: 3 files (1 biz, 2 svc)
    # tgt: 6 files (2 biz, 4 svc)
    
    expected_counts = {
        "Repository": 1,
        "dem_daq": 1,
        "comm": 3,
        "mng": 3,
        "mnger": 3,
        "tgt": 6
    }
    
    found_layers = {}

    for ctx in contexts:
        layer = ctx.layer
        count = len(ctx.code_snippets)
        print(f"Context Layer: {layer}, File Count: {count}")
        # Show last up to 4 parts to give context (keyword/layer/...)
        files = [os.path.join("...", *Path(s.path).parts[-4:]) for s in ctx.code_snippets]
        
        print(f"  Files: [")
        for f in files:
            print(f"    {f},")
        print(f"  ]")
        
        found_layers[layer] = count
        
        if layer in expected_counts:
            expected = expected_counts[layer]
            if count == expected:
                print(f"  [PASS] Layer '{layer}' count matches.")
            else:
                print(f"  [FAIL] Layer '{layer}' count mismatch. Expected {expected}, got {count}.")
        else:
             print(f"  [FAIL] Unexpected layer '{layer}'.")

    # Final Verification
    all_passed = True
    for layer, expected in expected_counts.items():
        if layer not in found_layers:
            print(f"  [FAIL] Missing layer '{layer}'.")
            all_passed = False
        elif found_layers[layer] != expected:
            all_passed = False
    
    if all_passed:
        print("\nSUCCESS: All expected groups and counts verified.")
    else:
        print("\nFAILURE: Some checks failed.")

if __name__ == "__main__":
    test_jdbc_context_generator()
