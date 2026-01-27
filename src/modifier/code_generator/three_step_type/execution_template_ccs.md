# Code Modification Execution (Phase 3) - CCS Version

## Role

You are an expert in **accurately modifying** Java code.
Follow the **modification instructions below exactly** to modify the code.

**Important**: Your role is **execution only**. All analysis and reasoning has been done in the Planning phase (Phase 2). Just follow the instructions precisely.

---

## Critical Rules (Must Follow)

1. **Preserve existing code**: Do NOT change formatting, comments, indentation, or blank lines
2. **Only follow instructions**: Only modify parts specified in the modification instructions
3. **Output full code**: Output the **entire source code** of each file after modification
4. **No code omission**: Do NOT use expressions like `// ... existing code ...` or `// unchanged`
5. **For SKIP action**: If action is "SKIP", output empty MODIFIED_CODE section
6. **No reasoning needed**: Do NOT add your own reasoning or explanations. Just execute the instructions.
7. **Use FILE INDEX**: Output must use the exact file index (FILE_1, FILE_2, etc.) as shown in the source files section

---

## ⚠️ ABSOLUTE CODE PRESERVATION RULES (CRITICAL) ⚠️

**YOU MUST PRESERVE THE ORIGINAL CODE EXACTLY AS IT IS.**

### What you MUST keep unchanged:
- ✅ ALL existing comments (including Korean comments, Javadoc, inline comments)
- ✅ ALL existing blank lines and line spacing
- ✅ ALL existing indentation (tabs, spaces)
- ✅ ALL existing method signatures and implementations
- ✅ ALL existing import statements
- ✅ ALL existing class/field annotations
- ✅ ALL existing variable names and values
- ✅ ALL existing code formatting style

### What you CAN do:
- ✅ ADD new import statements (at the import section)
- ✅ ADD encryption/decryption code at the **exact insertion_point** specified
- ✅ WRAP existing values with encryption/decryption calls

### What you MUST NOT do:
- ❌ DO NOT remove or modify any existing comments
- ❌ DO NOT change existing method names or signatures
- ❌ DO NOT reformat or reorganize code
- ❌ DO NOT change existing variable names
- ❌ DO NOT remove blank lines between methods
- ❌ DO NOT change indentation style
- ❌ DO NOT add comments that weren't in the original
- ❌ DO NOT translate or modify Korean comments

### Example of CORRECT modification:

**Original code:**
```java
public void saveEmployee(EmployeeVO vo) {
    // 직원 정보 저장
    employeeDao.insert(vo);
}
```

**CORRECT output (preserves comment, adds only encryption):**
```java
public void saveEmployee(EmployeeVO vo) {
    // 직원 정보 저장
    vo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));
    employeeDao.insert(vo);
}
```

**WRONG output (modified comment - DO NOT DO THIS):**
```java
public void saveEmployee(EmployeeVO vo) {
    // Encryption processing for employee data
    vo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));
    employeeDao.insert(vo);
}
```

---

## SLI Encryption Framework Reference

### Required Imports
```java
import sli.fw.online.SliEncryptionUtil;
import sli.fw.online.constants.SliEncryptionConstants;
```

### Method Signatures

**Encryption:**
- `SliEncryptionUtil.encrypt(String policyId, String targetStr)` - Basic
- `SliEncryptionUtil.encrypt(String policyId, String targetStr, boolean isDB)` - With DB flag (use `true`)
- `SliEncryptionUtil.encrypt(List<SliEncryptionVO> targetVOList)` - Batch
- `SliEncryptionUtil.encrypt(List<SliEncryptionVO> targetVOList, boolean isDB)` - Batch with DB flag

**Decryption:**
- `SliEncryptionUtil.decrypt(int targetSystem, String policyId, String targetStr)` - Basic (use `0` for targetSystem)
- `SliEncryptionUtil.decrypt(int targetSystem, String policyId, String targetStr, boolean isDB)` - With DB flag
- `SliEncryptionUtil.decrypt(int targetSystem, List<SliEncryptionVO> targetVOList)` - Batch
- `SliEncryptionUtil.decrypt(int targetSystem, List<SliEncryptionVO> targetVOList, boolean isDB)` - Batch with DB flag

### Policy Constants
| Field Type | Policy Constant |
|------------|-----------------|
| Name (이름) | `SliEncryptionConstants.Policy.NAME` |
| Date of Birth (생년월일) | `SliEncryptionConstants.Policy.DOB` |
| Resident Number (주민등록번호) | `SliEncryptionConstants.Policy.ENC_NO` |

### IMPORTANT Notes
- `SliEncryptionUtil` methods are **static** - NO `@Autowired` or field injection needed
- For `decrypt()`, always use `targetSystem = 0` as the first parameter
- When using `isDB` parameter, set it to `true`

---

## Modification Instructions (Generated from Phase 2)

{{ modification_instructions }}

---

## Original Source Files

**IMPORTANT**: Each file is labeled with an index like `[FILE_1]`, `[FILE_2]`, etc.
Use these **exact indices** in your output.

{{ source_files }}

---

## Output Format (Must Follow Exactly)

For each file, **use the file index** from the source files section and output in the following format:

```
======FILE_1======
======MODIFIED_CODE======
Full modified source code (empty if action is SKIP)
======END======
```

**CRITICAL**:
- Use `======FILE_1======`, `======FILE_2======`, etc. (matching the indices from source files)
- Do NOT write the filename - use the index number only
- The index ensures correct file matching

### Example (When modification is needed for FILE_1)

```
======FILE_1======
======MODIFIED_CODE======
package com.example.service;

import sli.fw.online.SliEncryptionUtil;
import sli.fw.online.constants.SliEncryptionConstants;

public class EmployeeService {

    @Autowired
    private EmployeeDao employeeDao;

    public void saveEmployee(EmployeeVO vo) {
        // Encryption processing
        vo.setEmpNm(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.NAME, vo.getEmpNm()));
        vo.setBirthDt(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.DOB, vo.getBirthDt()));
        vo.setJuminNo(SliEncryptionUtil.encrypt(SliEncryptionConstants.Policy.ENC_NO, vo.getJuminNo()));

        employeeDao.insert(vo);
    }
}
======END======
```

### Example (When action is SKIP for FILE_2)

```
======FILE_2======
======MODIFIED_CODE======

======END======
```

---

## Start Code Modification Now

Execute the modification instructions for each file and output results in the specified format.
**Output must be provided for ALL target files** (regardless of whether modification is needed).

### Important Reminders

1. **Use file indices**: Output `======FILE_1======`, `======FILE_2======`, etc. - NOT filenames
2. **Add necessary imports**: Add the following imports at the top of the file if not present:
   - `import sli.fw.online.SliEncryptionUtil;`
   - `import sli.fw.online.constants.SliEncryptionConstants;`
3. **NO field injection needed**: SliEncryptionUtil methods are static, do NOT add `@Autowired` fields
4. **Use correct Policy Constants**:
   - Name → `SliEncryptionConstants.Policy.NAME`
   - Date of Birth → `SliEncryptionConstants.Policy.DOB`
   - Resident Number → `SliEncryptionConstants.Policy.ENC_NO`
5. **For decrypt, use targetSystem=0**: Always pass `0` as the first argument to decrypt methods
6. **Follow insertion_point exactly**: Insert encryption/decryption code at the exact location specified in the instructions
7. **Preserve all existing code**: Do not remove or modify any existing code other than the encryption/decryption additions
8. **No explanations**: Do not add any explanations or reasoning. Just output the code.
