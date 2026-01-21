# Encryption/Decryption Modification Planning (Phase 2)

## Role

You are an expert in analyzing **Data Flow** in Java Spring Boot legacy systems.
Based on the information below, output specific modification instructions in JSON format describing **where**, **what**, and **how** to insert encryption/decryption logic.

**Important**: Your role is **analysis and planning**. Actual code writing will be done in the next step.

---

## Encryption Framework Information (KSign)

This project uses the **KSign** encryption framework with `ksignUtil`:

### Encryption/Decryption Methods
- **Encryption**: `ksignUtil.ksignEnc(policyId, inputValue)` - Returns encrypted string
- **Decryption**: `ksignUtil.ksignDec(policyId, inputValue)` - Returns decrypted string

### Policy IDs (★ ONLY these 3 fields are encryption targets)
| Field Type | Policy ID | Column Name Patterns |
|------------|-----------|---------------------|
| **Name (이름)** | `"P017"` | name, userName, user_name, fullName, firstName, lastName, custNm, CUST_NM, empNm, EMP_NM |
| **Date of Birth (생년월일)** | `"P018"` | dob, dateOfBirth, birthDate, birthday, dayOfBirth, birthDt, BIRTH_DT |
| **Resident Number (주민번호)** | `"P019"` | jumin, juminNumber, ssn, residentNumber, juminNo, JUMIN_NO, residentNo |

### Important: Only 3 Field Types
**ONLY encrypt/decrypt the above 3 field types (Name, DOB, Jumin).**
Other fields like phone, address, gender, etc. are **NOT** encryption targets - do NOT add encryption for them.

---

## Analysis Target Information

### ★★★ Target Table/Column Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table specified below.**

This is the specific table that requires encryption/decryption modifications. Analyze the data flow ONLY for operations involving this table.

{{ table_info }}

**Instructions:**
1. Only analyze SQL queries that access the **target table** above
2. Only analyze methods that are part of call chains leading to the **target table**
3. Generate modification instructions ONLY for files involved in **target table** operations

### VO Field Mapping & SQL Usage Summary (★ Pre-analyzed from Phase 1)

The following is a **comprehensive** VO and SQL mapping extracted from the previous analysis phase.
This vo_info contains ALL the information you need about VO fields and SQL queries.

**vo_info Structure:**
1. **vo_mappings**: Each VO class with field details
   - `field_name`, `getter`, `setter`: For code generation
   - `policy_id`: P017 (name), P018 (DOB), P019 (jumin)
   - `mapped_sql_columns` and `mapped_sql_aliases`: SQL column mappings

2. **sql_column_usage**: SQL query summary
   - `query_id`: Maps to DAO method name
   - `query_type`: SELECT, INSERT, UPDATE, DELETE
   - `encryption_target_columns`: Columns that need encryption/decryption
   - `target_vo_class`: Which VO class is used for this query

**Use this information to:**
- Determine which methods call which SQL queries (via query_id)
- Identify what crypto action is needed (INSERT/UPDATE → ENCRYPT, SELECT → DECRYPT)
- Generate accurate getter/setter calls using vo_mappings

{{ vo_info }}

### Method Call Chain (Endpoint → SQL)
Call path from controller to SQL:
{{ call_stacks }}

### Source Files to Modify ({{ file_count }} files)
{{ source_files }}

### Current Layer: {{ layer_name }}

---

## Analysis Guidelines

### 1. Data Flow Analysis (Per Call Chain)
**For each call chain in call_stacks**, analyze the data flow:
1. Identify the SQL query type from `vo_info.sql_column_usage` (match by query_id ↔ DAO method)
2. Determine crypto action:
   - **INSERT/UPDATE queries** → Encryption needed **before** saving to DB
   - **SELECT queries** → Decryption needed **after** retrieving from DB
3. Generate modification instructions for each flow

### 2. Using VO Field Mapping (from vo_info)
From the vo_info.vo_mappings:
- Use `getter` and `setter` names for generating code patterns
- Use `policy_id` to determine which policy ID to use (P017, P018, P019)
- Use `mapped_sql_columns` to match VO fields with SQL query columns

From the vo_info.sql_column_usage:
- Use `query_id` to match call chain methods with SQL queries
- Use `query_type` to determine ENCRYPT (INSERT/UPDATE) or DECRYPT (SELECT)
- Use `encryption_target_columns` to verify which columns need crypto

### 3. Modification Location Decision
- Service layer **before/after** DAO/Mapper calls is the typical modification location
- If Controller directly calls DAO, modify in Controller

### 4. Minimize Modification Scope
- Maintain existing code structure and logic as much as possible
- Only add encryption/decryption logic
- Do not modify unnecessary files

---

## Output Format (Must output in JSON format)

```json
{
  "data_flow_analysis": {
    "overview": "Overview of the entire data flow (2-3 sentences)",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "User Registration Flow",
        "direction": "INBOUND_TO_DB",
        "data_source": {
          "type": "HTTP_REQUEST | SESSION | DB | EXTERNAL_API",
          "description": "Where the data comes from"
        },
        "data_sink": {
          "type": "DB | HTTP_RESPONSE | SESSION | EXTERNAL_API",
          "description": "Where the data goes to"
        },
        "path": "Controller.method() → Service.method() → DAO.method() → DB",
        "sensitive_columns": ["last_name", "jumin_number"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "Before DB save (in Service layer)"
      }
    ],
    "layer_responsibilities": {
      "controller": "Handles HTTP request/response, only passes data",
      "service": "Business logic, handles encryption/decryption",
      "dao": "Only handles DB access, passes encrypted data as-is"
    }
  },
  "modification_instructions": [
    {
      "file_name": "File name (e.g., UserService.java)",
      "target_method": "Method name to modify",
      "action": "ENCRYPT | DECRYPT | SKIP",
      "reason": "Reason for this modification (or reason for SKIP)",
      "target_columns": [
        {
          "column_name": "Column name in code/VO (e.g., empNm, birthDt)",
          "policy_id": "Policy ID for this field type (P017, P018, or P019)"
        }
      ],
      "insertion_point": "Code insertion location description (e.g., 'right before dao.insert(list) call')",
      "data_object_name": "Target object name for encryption/decryption (e.g., list, userVO, reqData)",
      "code_pattern_hint": "Code pattern hint to insert"
    }
  ]
}
```

### Field Descriptions

| Field | Description | Example |
|-------|-------------|---------|
| `file_name` | File name to modify | `UserService.java`, `EmpController.java` |
| `target_method` | Method name to modify | `saveUser`, `getUserList` |
| `action` | Action to perform | `ENCRYPT`, `DECRYPT`, `SKIP` |
| `target_columns` | Columns to encrypt/decrypt (ONLY name, DOB, jumin) | `[{"column_name": "empNm", "policy_id": "P017"}]` |
| `insertion_point` | Insertion location description | `right before dao.insert() call`, `right before return list;` |
| `data_object_name` | Target data object | `list`, `userVO`, `result` |
| `code_pattern_hint` | Code pattern example | `vo.setEmpNm(ksignUtil.ksignEnc("P017", vo.getEmpNm()));` |

### Important Notes

1. **When action is SKIP**: Specify in `reason` why the file/method does not need modification
2. **target_columns**: ONLY include name (P017), DOB (P018), or jumin (P019) fields. Do NOT include other fields.
3. **insertion_point**: Describe specifically so code can be inserted in the next step
4. **code_pattern_hint**: Use `ksignUtil.ksignEnc(policyId, value)` for encryption, `ksignUtil.ksignDec(policyId, value)` for decryption
5. **Use vo_info mapping**: Reference the getter/setter names from vo_info for accurate code patterns

---

## Critical Encryption/Decryption Rules

### Core Principle: Encrypt/Decrypt ONLY when data crosses the DB boundary

| Data Source | Data Sink | Action | Reason |
|-------------|-----------|--------|--------|
| HTTP_REQUEST | DB | **ENCRYPT** | Plaintext from client must be encrypted before DB storage |
| DB | HTTP_RESPONSE | **DECRYPT** | Encrypted data from DB must be decrypted before sending to client |
| DB | EXTERNAL_API | **DECRYPT** | External systems expect plaintext data |
| EXTERNAL_API | DB | **ENCRYPT** | Data from external systems must be encrypted before DB storage |
| SESSION | DB | **ENCRYPT** | Session data is plaintext, must be encrypted for DB |
| DB | SESSION | **DECRYPT** | Encrypted DB data must be decrypted for session storage |
| SESSION | HTTP_RESPONSE | **NONE** | Session data is already plaintext, no decryption needed |
| HTTP_REQUEST | SESSION | **NONE** | No DB involved, no encryption needed |

### ⚠️ CRITICAL: Session Data is ALWAYS Plaintext - NEVER Decrypt

**Session data has already been decrypted during login.** When you see code like:
```java
MemberVO member = (MemberVO) session.getAttribute("member");
String userName = member.getUserNm();  // This is ALREADY plaintext!
```

**DO NOT decrypt session data!** The decryption already happened when the user logged in (DB → Session flow).

| Pattern | Action | Reason |
|---------|--------|--------|
| `session.getAttribute(...)` → use data | **NO DECRYPT** | Session stores plaintext |
| `session.getAttribute(...)` → save to DB | **ENCRYPT only** | Plaintext → DB needs encryption |
| `session.getAttribute(...)` → return to client | **NO DECRYPT** | Already plaintext |

### Special Case: SELECT with WHERE clause on sensitive columns

When a SELECT query has a WHERE clause that references sensitive columns (name, DOB, or jumin):
1. **First**: ENCRYPT the search parameter (to match encrypted data in DB)
2. **Then**: Execute the query
3. **Finally**: DECRYPT the result (to return plaintext to caller)

---

## Example Output

### Example: Basic INSERT and SELECT

**Input Summary:**
- INSERT query with emp_nm, birth_dt, jumin_no
- SELECT query returning the same columns
- vo_info shows: empNm→P017, birthDt→P018, juminNo→P019
- Service layer calls DAO

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "The employee table stores user information. INSERT requires encryption before DB save, SELECT requires decryption after DB retrieval.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Employee Registration (INSERT)",
        "direction": "INBOUND_TO_DB",
        "data_source": {"type": "HTTP_REQUEST", "description": "Client POST request"},
        "data_sink": {"type": "DB", "description": "INSERT into employee"},
        "path": "Controller → Service.save() → DAO.insert() → DB",
        "sensitive_columns": ["emp_nm", "birth_dt", "jumin_no"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "In Service, right before DAO call"
      },
      {
        "flow_id": "FLOW_002",
        "flow_name": "Employee Retrieval (SELECT)",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {"type": "DB", "description": "SELECT from employee"},
        "data_sink": {"type": "HTTP_RESPONSE", "description": "JSON response"},
        "path": "DB → DAO.select() → Service.get() → Controller → Client",
        "sensitive_columns": ["emp_nm", "birth_dt", "jumin_no"],
        "crypto_action": "DECRYPT",
        "crypto_timing": "In Service, right after DAO return"
      }
    ],
    "layer_responsibilities": {
      "controller": "HTTP handling only",
      "service": "Encryption/decryption logic here",
      "dao": "DB access only"
    }
  },
  "modification_instructions": [
    {
      "file_name": "EmployeeService.java",
      "target_method": "saveEmployee",
      "action": "ENCRYPT",
      "reason": "FLOW_001: Encrypt before DB storage",
      "target_columns": [
        {"column_name": "empNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"},
        {"column_name": "juminNo", "policy_id": "P019"}
      ],
      "insertion_point": "Right before employeeDao.insert(vo) call",
      "data_object_name": "vo",
      "code_pattern_hint": "vo.setEmpNm(ksignUtil.ksignEnc(\"P017\", vo.getEmpNm()));\nvo.setBirthDt(ksignUtil.ksignEnc(\"P018\", vo.getBirthDt()));\nvo.setJuminNo(ksignUtil.ksignEnc(\"P019\", vo.getJuminNo()));"
    },
    {
      "file_name": "EmployeeService.java",
      "target_method": "getEmployeeById",
      "action": "DECRYPT",
      "reason": "FLOW_002: Decrypt after DB retrieval",
      "target_columns": [
        {"column_name": "empNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"},
        {"column_name": "juminNo", "policy_id": "P019"}
      ],
      "insertion_point": "Right after DAO return, before return statement",
      "data_object_name": "result",
      "code_pattern_hint": "result.setEmpNm(ksignUtil.ksignDec(\"P017\", result.getEmpNm()));\nresult.setBirthDt(ksignUtil.ksignDec(\"P018\", result.getBirthDt()));\nresult.setJuminNo(ksignUtil.ksignDec(\"P019\", result.getJuminNo()));"
    }
  ]
}
```

---

## Start Analysis Now

Based on the information above:
1. **For each call chain in call_stacks**, analyze the data flow using:
   - `vo_info.vo_mappings` for field details (getter, setter, policy_id)
   - `vo_info.sql_column_usage` for SQL query information (query_id, query_type)
2. **Output modification instructions** for each flow in JSON format
3. **SKIP** flows that don't involve the target table's encryption columns

**Important**:
- Use vo_info field mappings to generate accurate getter/setter calls in `code_pattern_hint`
- Match call chain methods with sql_column_usage via query_id to determine crypto action

**Remember**: Focus on the target table. Only include modification instructions for operations that interact with the target table.
