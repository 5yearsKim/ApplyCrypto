"""
Test script for DiffCodePatcher.
Reads the original file from examples/EmployeeService.java, creates a modified copy,
applies the unified diff, and validates the result.
"""
import sys
import os
import shutil
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("applycrypto")

# Add src to sys.path to import modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT / "src"))

from modifier.code_patcher.diff_code_patcher import DiffCodePatcher

# Define paths for the test
TEST_DIR = Path(__file__).parent
ORIGINAL_FILE = TEST_DIR / "EmployeeService.java"
OUTPUT_FILE = TEST_DIR / "EmployeeService.java.modified"

# The diff content to apply (from user-provided data)
# Note: The line numbers in the diff may not match exactly with the actual file.
# This test validates if the DiffCodePatcher can correctly apply the diff.
# Paths are updated to match the local file validation requirements.
DIFF_CONTENT = r"""--- a/examples/EmployeeService.java
+++ b/examples/EmployeeService.java.modified
@@ -27,7 +27,9 @@
 		for (Employee employee : employees) {
-			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+			employee.setLastName(k_sign.CryptoService.decrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+			employee.setDayOfBirth(k_sign.CryptoService.decrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		}
 		return employees;
 	}
@@ -40,7 +42,9 @@
 	public void update(Employee employee)
 	{
-		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+		employee.setLastName(k_sign.CryptoService.encrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+		employee.setDayOfBirth(k_sign.CryptoService.encrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		employeeMapper.updateEmp(employee);
 	}
@@ -47,7 +51,9 @@
 	public void save(Employee employee) {
 		Department dept = deptMapper.getDeptById(employee.getDept().getId());
 		employee.setDept(dept);
-		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+		employee.setJuminNumber(k_sign.CryptoService.encrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+		employee.setLastName(k_sign.CryptoService.encrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+		employee.setDayOfBirth(k_sign.CryptoService.encrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		employeeMapper.addEmp(employee);
 	}
@@ -54,7 +60,9 @@
 	public Employee getEmpById(Integer id) {
 		Employee employee = employeeMapper.getEmpById(id);
-		employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+		employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+		employee.setLastName(k_sign.CryptoService.decrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+		employee.setDayOfBirth(k_sign.CryptoService.decrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		return employee;
 	}
@@ -60,7 +68,9 @@
 	public List<Employee> getEmpsByPage(Integer pageIndex,Integer size) {
 		List<Employee> employees = employeeMapper.getEmpsByPage(pageIndex,size);
 		for (Employee employee : employees) {
-			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+			employee.setLastName(k_sign.CryptoService.decrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+			employee.setDayOfBirth(k_sign.CryptoService.decrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		}
 		return employees;
 	}
@@ -71,7 +81,9 @@
 	public List<Employee>  query(String condition) {
 		List<Employee> employees = employeeMapper.query(condition);
 		for (Employee employee : employees) {
-			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.K_SIGN_SSM));
+			employee.setJuminNumber(k_sign.CryptoService.decrypt(employee.getJuminNumber(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+			employee.setLastName(k_sign.CryptoService.decrypt(employee.getLastName(), k_sign.CryptoService.P20, K_SIGN_NAME));
+			employee.setDayOfBirth(k_sign.CryptoService.decrypt(employee.getDayOfBirth(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		}
 		return employees;
 	}
@@ -80,7 +92,9 @@
 	public List<Map<String, Object>> getDatas() {
 		List<Map<String, Object>> data = employeeMapper.getDatas();
 		for (Map<String, Object> map : data) {
-			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.K_SIGN_SSM));
+			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+			map.put("lastName", k_sign.CryptoService.decrypt(map.get("lastName").toString(), k_sign.CryptoService.P20, K_SIGN_NAME));
+			map.put("dayOfBirth", k_sign.CryptoService.decrypt(map.get("dayOfBirth").toString(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		}
 		return data;
 	}
@@ -87,7 +101,9 @@
 	public List<Map<String, Object>> getPer() {
 		List<Map<String, Object>> per = employeeMapper.getPer();
 		for (Map<String, Object> map : per) {
-			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.K_SIGN_SSM));
+			map.put("juminNumber", k_sign.CryptoService.decrypt(map.get("juminNumber").toString(), k_sign.CryptoService.P10, K_SIGN_JUMIN));
+			map.put("lastName", k_sign.CryptoService.decrypt(map.get("lastName").toString(), k_sign.CryptoService.P20, K_SIGN_NAME));
+			map.put("dayOfBirth", k_sign.CryptoService.decrypt(map.get("dayOfBirth").toString(), k_sign.CryptoService.P30, K_SIGN_DOB));
 		}
 		return per;
 	}
@@ -112,50 +128,47 @@
"""

def validate_patch_result(content: str) -> dict:
    """
    Validate that the patch was applied correctly.
    Returns a dict with validation results for each expected change.
    """
    results = {}

    # Check for new tokens that should exist after patching
    expected_new_tokens = [
        "K_SIGN_JUMIN",
        "K_SIGN_NAME",
        "K_SIGN_DOB",
        "setLastName",
        "setDayOfBirth",
        "P10",
        "P20",
        "P30",
    ]
    
    for token in expected_new_tokens:
        results[f"has_{token}"] = token in content
    
    # Check that old tokens should NOT exist after patching
    old_tokens = ["K_SIGN_SSM"]
    for token in old_tokens:
        results[f"removed_{token}"] = token not in content
    
    return results


def main():
    print("=" * 60)
    print("=== Running DiffCodePatcher Test ===")
    print("=" * 60)
    
    # 1. Setup the modified file (copy from original)
    if not ORIGINAL_FILE.exists():
        print(f"[Error] Original file not found: {ORIGINAL_FILE}")
        return

    shutil.copy(ORIGINAL_FILE, OUTPUT_FILE)
    print(f"[Setup] Copied {ORIGINAL_FILE.name} -> {OUTPUT_FILE.name}")
    
    try:
        # 2. Read original content (for comparison/info only)
        with open(ORIGINAL_FILE, "r", encoding="utf-8") as f:
            original_content = f.read()
        
        original_lines = original_content.splitlines()
        print(f"\n[Original] File: {ORIGINAL_FILE.name}")
        
        # Show lines that will be changed (lines with K_SIGN_SSM)
        print("\n--- Lines containing 'K_SIGN_SSM' (to be replaced) ---")
        for i, line in enumerate(original_lines, 1):
            if "K_SIGN_SSM" in line:
                print(f"  Line {i}: {line.strip()[:80]}...")
        print("-" * 50)

        # 3. Initialize the patcher
        patcher = DiffCodePatcher(project_root=PROJECT_ROOT)

        # 4. Apply the patch to OUTPUT_FILE
        print(f"\n[Action] Applying diff patch to {OUTPUT_FILE.name}...")
        success, error = patcher.apply_patch(OUTPUT_FILE, DIFF_CONTENT)

        # 5. Check results
        if success:
            print("\n[Result] Patch applied successfully!")
            
            with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
                new_content = f.read()
            
            new_lines = new_content.splitlines()
            print(f"[Modified] Lines: {len(new_lines)} (+{len(new_lines) - len(original_lines)} lines)")
            print(f"[Modified] Size: {len(new_content)} bytes")
            
            # 6. Validate the changes
            print("\n--- Validation Results ---")
            validation = validate_patch_result(new_content)
            
            all_passed = True
            for check, passed in validation.items():
                status = "✓ PASS" if passed else "✗ FAIL"
                print(f"  {status}: {check}")
                if not passed:
                    all_passed = False
            
            print("-" * 50)
            
            if all_passed:
                print("\n[OVERALL] All validations PASSED!")
            else:
                print("\n[OVERALL] Some validations FAILED!")
            
            # 7. Show modified lines with new tokens
            print("\n--- Lines containing new tokens ---")
            for i, line in enumerate(new_lines, 1):
                if any(token in line for token in ["K_SIGN_JUMIN", "K_SIGN_NAME", "K_SIGN_DOB"]):
                    print(f"  Line {i}: {line.strip()[:80]}...")
                    
        else:
            print(f"\n[Error] Failed to apply patch: {error}")
            
    except Exception as e:
        print(f"\n[Exception] An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print(f"\n[Note] Modified file saved at: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()