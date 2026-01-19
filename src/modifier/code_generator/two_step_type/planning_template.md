# Encryption/Decryption Modification Planning (Planning Phase)

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

### Target Table/Column Information for Encryption
{{ table_info }}

### SQL Query Analysis (★ Core Data Flow Information)
The following are actual SQL queries accessing this table. **Query type (SELECT/INSERT/UPDATE/DELETE)** determines encryption/decryption location:
{{ sql_queries }}

### Method Call Chain (Endpoint → SQL)
Call path from controller to SQL:
{{ call_stacks }}

### Source Files to Modify ({{ file_count }} files)
{{ source_files }}

{% if context_files %}
### Reference Files (VO/DTO Classes - Not to be modified)
Reference files for understanding data structures:
{{ context_files }}
{% endif %}

### Current Layer: {{ layer_name }}

---

## Analysis Guidelines

### 1. Data Flow Analysis
Analyze SQL queries and call chains to understand how data flows:
- **INSERT/UPDATE queries** → Encryption needed **before** saving to DB
- **SELECT queries** → Decryption needed **after** retrieving from DB

### 2. Modification Location Decision
- Service layer **before/after** DAO/Mapper calls is the typical modification location
- If Controller directly calls DAO, modify in Controller

### 3. Minimize Modification Scope
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

**Common Mistake to Avoid:**
```java
// ❌ WRONG - DO NOT DO THIS
MemberVO member = (MemberVO) session.getAttribute("member");
member.setUserNm(ksignUtil.ksignDec("P017", member.getUserNm()));  // WRONG!

// ✅ CORRECT - Session data is already plaintext, use as-is
MemberVO member = (MemberVO) session.getAttribute("member");
String userName = member.getUserNm();  // Already plaintext, just use it
```

### Special Case: SELECT with WHERE clause on sensitive columns

When a SELECT query has a WHERE clause that references sensitive columns (name, DOB, or jumin):
1. **First**: ENCRYPT the search parameter (to match encrypted data in DB)
2. **Then**: Execute the query
3. **Finally**: DECRYPT the result (to return plaintext to caller)

```
Example: SELECT empNm, birthDt FROM employee WHERE empNm = #{searchName}
→ Step 1: Encrypt searchName with ksignUtil.ksignEnc("P017", searchName)
→ Step 2: Execute query (matches encrypted name in DB)
→ Step 3: Decrypt result's empNm with ksignUtil.ksignDec("P017", empNm)
         Decrypt result's birthDt with ksignUtil.ksignDec("P018", birthDt)
```

---

## Examples

### Example 1: Basic INSERT and SELECT (HTTP ↔ DB)

**Input:**
- SQL 1: `INSERT INTO employee (emp_nm, birth_dt, jumin_no) VALUES (#{empNm}, #{birthDt}, #{juminNo})`
- SQL 2: `SELECT emp_nm, birth_dt, jumin_no FROM employee WHERE id = #{id}`
- Method chain 1: `EmpController.save()` → `EmployeeService.saveEmployee()` → `EmployeeDao.insert()`
- Method chain 2: `EmpController.getEmployee()` → `EmployeeService.getEmployeeById()` → `EmployeeDao.selectById()`

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "The employee table stores user information, with emp_nm (name), birth_dt (DOB), and jumin_no (resident number) as sensitive data requiring encryption. Data from HTTP requests needs encryption before DB save, and data from DB needs decryption before response.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Employee Registration (INSERT)",
        "direction": "INBOUND_TO_DB",
        "data_source": {
          "type": "HTTP_REQUEST",
          "description": "Client sends employee information via POST request"
        },
        "data_sink": {
          "type": "DB",
          "description": "INSERT into employee table"
        },
        "path": "EmpController.save() → EmployeeService.saveEmployee() → EmployeeDao.insert() → DB",
        "sensitive_columns": ["emp_nm", "birth_dt", "jumin_no"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "In Service layer, right before DAO call"
      },
      {
        "flow_id": "FLOW_002",
        "flow_name": "Employee Retrieval (SELECT)",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {
          "type": "DB",
          "description": "SELECT from employee table"
        },
        "data_sink": {
          "type": "HTTP_RESPONSE",
          "description": "Return as JSON response to client"
        },
        "path": "DB → EmployeeDao.selectById() → EmployeeService.getEmployeeById() → EmpController.getEmployee() → Client",
        "sensitive_columns": ["emp_nm", "birth_dt", "jumin_no"],
        "crypto_action": "DECRYPT",
        "crypto_timing": "In Service layer, right after DAO return"
      }
    ],
    "layer_responsibilities": {
      "controller": "Only handles HTTP request/response, no encryption logic",
      "service": "Handles business logic, key location for encryption/decryption",
      "dao": "Only handles DB access, receives and stores encrypted data as-is"
    }
  },
  "modification_instructions": [
    {
      "file_name": "EmployeeService.java",
      "target_method": "saveEmployee",
      "action": "ENCRYPT",
      "reason": "FLOW_001: Encryption needed before saving HTTP request data to DB",
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
      "reason": "FLOW_002: Decryption needed before returning encrypted data from DB to client",
      "target_columns": [
        {"column_name": "empNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"},
        {"column_name": "juminNo", "policy_id": "P019"}
      ],
      "insertion_point": "Right after employeeDao.selectById(id) return, before return statement",
      "data_object_name": "employee",
      "code_pattern_hint": "employee.setEmpNm(ksignUtil.ksignDec(\"P017\", employee.getEmpNm()));\nemployee.setBirthDt(ksignUtil.ksignDec(\"P018\", employee.getBirthDt()));\nemployee.setJuminNo(ksignUtil.ksignDec(\"P019\", employee.getJuminNo()));"
    },
    {
      "file_name": "EmpController.java",
      "target_method": "any",
      "action": "SKIP",
      "reason": "Controller only handles data passing, encryption/decryption is handled in Service layer",
      "target_columns": [],
      "insertion_point": "",
      "data_object_name": "",
      "code_pattern_hint": ""
    }
  ]
}
```

---

### Example 2: SELECT with WHERE clause on sensitive column (Search scenario)

**Input:**
- SQL: `SELECT id, cust_nm, birth_dt FROM customer WHERE cust_nm = #{custNm}`
- Method chain: `SearchController.search()` → `CustomerService.searchByName()` → `CustomerDao.selectByName()`

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Search functionality queries customer table using name as search criteria. Since cust_nm is encrypted in DB, search parameter must be encrypted first to match, then results must be decrypted for display.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Customer Search with Encrypted WHERE",
        "direction": "BIDIRECTIONAL",
        "data_source": {
          "type": "HTTP_REQUEST",
          "description": "Search parameter (name) from user input"
        },
        "data_sink": {
          "type": "HTTP_RESPONSE",
          "description": "Search results returned to client"
        },
        "path": "SearchController.search() → CustomerService.searchByName() → CustomerDao.selectByName() → DB → (result) → CustomerService → SearchController → Client",
        "sensitive_columns": ["cust_nm", "birth_dt"],
        "crypto_action": "ENCRYPT_THEN_DECRYPT",
        "crypto_timing": "ENCRYPT search param before DAO call, DECRYPT results after DAO return"
      }
    ],
    "layer_responsibilities": {
      "controller": "Receives search request, returns results",
      "service": "1) Encrypts search parameters, 2) Calls DAO, 3) Decrypts results",
      "dao": "Executes query with encrypted parameters"
    }
  },
  "modification_instructions": [
    {
      "file_name": "CustomerService.java",
      "target_method": "searchByName",
      "action": "ENCRYPT_THEN_DECRYPT",
      "reason": "FLOW_001: Search param must be encrypted to match DB data, results must be decrypted for response",
      "target_columns": [
        {"column_name": "custNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"}
      ],
      "insertion_point": "ENCRYPT: Right before customerDao.selectByName() call; DECRYPT: Right after DAO return",
      "data_object_name": "searchParam (for encrypt), resultList (for decrypt)",
      "code_pattern_hint": "// Before DAO call: encrypt search parameter\nsearchParam.setCustNm(ksignUtil.ksignEnc(\"P017\", searchParam.getCustNm()));\nList<Customer> resultList = customerDao.selectByName(searchParam);\n// After DAO call: decrypt results\nfor (Customer c : resultList) {\n    c.setCustNm(ksignUtil.ksignDec(\"P017\", c.getCustNm()));\n    c.setBirthDt(ksignUtil.ksignDec(\"P018\", c.getBirthDt()));\n}"
    }
  ]
}
```

---

### Example 3: Session data to DB (Session → DB)

**Input:**
- SQL: `INSERT INTO audit_log (user_nm, action, ip_address) VALUES (#{userNm}, #{action}, #{ipAddress})`
- Method chain: `AuditService.logAction()` → `AuditDao.insertLog()`
- Note: `userNm` is retrieved from HTTP Session (already plaintext)

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Audit logging saves user action with user name from session. Session data is already plaintext (was decrypted when user logged in), so only encryption is needed before DB save. DO NOT decrypt session data.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Audit Log Insert (Session → DB)",
        "direction": "INBOUND_TO_DB",
        "data_source": {
          "type": "SESSION",
          "description": "User name retrieved from HTTP session (already plaintext)"
        },
        "data_sink": {
          "type": "DB",
          "description": "INSERT into audit_log table"
        },
        "path": "Session → AuditService.logAction() → AuditDao.insertLog() → DB",
        "sensitive_columns": ["user_nm"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "In Service layer, right before DAO call. DO NOT decrypt session data."
      }
    ],
    "layer_responsibilities": {
      "controller": "Not involved in this flow",
      "service": "Gets plaintext from session, encrypts before DB save",
      "dao": "Stores encrypted data"
    }
  },
  "modification_instructions": [
    {
      "file_name": "AuditService.java",
      "target_method": "logAction",
      "action": "ENCRYPT",
      "reason": "FLOW_001: Session data is plaintext, must encrypt before DB storage. No decryption needed for session data.",
      "target_columns": [
        {"column_name": "userNm", "policy_id": "P017"}
      ],
      "insertion_point": "Right before auditDao.insertLog() call",
      "data_object_name": "logData",
      "code_pattern_hint": "logData.setUserNm(ksignUtil.ksignEnc(\"P017\", logData.getUserNm()));"
    }
  ]
}
```

---

### Example 4: DB to External API (DB → External System)

**Input:**
- SQL: `SELECT mem_nm, birth_dt, jumin_no FROM member WHERE id = #{memberId}`
- Method chain: `IntegrationController.sendToPartner()` → `MemberService.getMemberForExport()` → `MemberDao.selectById()` → `ExternalApiClient.sendMemberInfo()`
- Note: External partner system expects plaintext data

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Member data is retrieved from DB and sent to external partner API. External systems expect plaintext, so encrypted DB data must be decrypted before sending to external API.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Member Export to External API",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {
          "type": "DB",
          "description": "SELECT member data (encrypted in DB)"
        },
        "data_sink": {
          "type": "EXTERNAL_API",
          "description": "Partner system API expects plaintext"
        },
        "path": "DB → MemberDao.selectById() → MemberService.getMemberForExport() → ExternalApiClient.sendMemberInfo() → Partner System",
        "sensitive_columns": ["mem_nm", "birth_dt", "jumin_no"],
        "crypto_action": "DECRYPT",
        "crypto_timing": "In Service layer, after DAO return, before sending to external API"
      }
    ],
    "layer_responsibilities": {
      "controller": "Initiates export request",
      "service": "Retrieves encrypted data from DB, decrypts for external system",
      "dao": "Returns encrypted data from DB",
      "external_client": "Sends plaintext to partner"
    }
  },
  "modification_instructions": [
    {
      "file_name": "MemberService.java",
      "target_method": "getMemberForExport",
      "action": "DECRYPT",
      "reason": "FLOW_001: External API expects plaintext. Must decrypt DB data before sending to partner system.",
      "target_columns": [
        {"column_name": "memNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"},
        {"column_name": "juminNo", "policy_id": "P019"}
      ],
      "insertion_point": "Right after memberDao.selectById() return, before externalApiClient.sendMemberInfo() call",
      "data_object_name": "memberData",
      "code_pattern_hint": "memberData.setMemNm(ksignUtil.ksignDec(\"P017\", memberData.getMemNm()));\nmemberData.setBirthDt(ksignUtil.ksignDec(\"P018\", memberData.getBirthDt()));\nmemberData.setJuminNo(ksignUtil.ksignDec(\"P019\", memberData.getJuminNo()));"
    }
  ]
}
```

---

### Example 5: External API to DB (External System → DB)

**Input:**
- SQL: `INSERT INTO external_customer (cust_nm, birth_dt) VALUES (#{custNm}, #{birthDt})`
- Method chain: `WebhookController.receiveCustomer()` → `ExternalCustomerService.saveFromPartner()` → `ExternalCustomerDao.insert()`
- Note: Data received from external partner system (plaintext)

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Customer data received from external partner webhook. External data arrives as plaintext and must be encrypted before storing in our DB.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "External Customer Import",
        "direction": "INBOUND_TO_DB",
        "data_source": {
          "type": "EXTERNAL_API",
          "description": "Partner system sends customer data via webhook (plaintext)"
        },
        "data_sink": {
          "type": "DB",
          "description": "INSERT into external_customer table"
        },
        "path": "Partner System → WebhookController.receiveCustomer() → ExternalCustomerService.saveFromPartner() → ExternalCustomerDao.insert() → DB",
        "sensitive_columns": ["cust_nm", "birth_dt"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "In Service layer, right before DAO call"
      }
    ],
    "layer_responsibilities": {
      "controller": "Receives webhook payload",
      "service": "Encrypts external plaintext data before DB save",
      "dao": "Stores encrypted data"
    }
  },
  "modification_instructions": [
    {
      "file_name": "ExternalCustomerService.java",
      "target_method": "saveFromPartner",
      "action": "ENCRYPT",
      "reason": "FLOW_001: External API data is plaintext, must encrypt before DB storage",
      "target_columns": [
        {"column_name": "custNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"}
      ],
      "insertion_point": "Right before externalCustomerDao.insert() call",
      "data_object_name": "customerData",
      "code_pattern_hint": "customerData.setCustNm(ksignUtil.ksignEnc(\"P017\", customerData.getCustNm()));\ncustomerData.setBirthDt(ksignUtil.ksignEnc(\"P018\", customerData.getBirthDt()));"
    }
  ]
}
```

---

### Example 6: DB to Session storage (Login scenario)

**Input:**
- SQL: `SELECT user_id, user_nm, birth_dt FROM users WHERE login_id = #{loginId}`
- Method chain: `LoginController.login()` → `AuthService.authenticate()` → `UserDao.selectByLoginId()` → Session storage
- Note: After successful login, user info is stored in session for later use

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "User authentication retrieves user data from DB and stores in session. Session should store plaintext for easy access throughout the user's session, so DB data must be decrypted before session storage.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "User Login (DB → Session)",
        "direction": "DB_TO_OUTBOUND",
        "data_source": {
          "type": "DB",
          "description": "SELECT user info (encrypted in DB)"
        },
        "data_sink": {
          "type": "SESSION",
          "description": "Store user info in HTTP session (as plaintext)"
        },
        "path": "DB → UserDao.selectByLoginId() → AuthService.authenticate() → Session",
        "sensitive_columns": ["user_nm", "birth_dt"],
        "crypto_action": "DECRYPT",
        "crypto_timing": "In Service layer, after DAO return, before storing in session"
      }
    ],
    "layer_responsibilities": {
      "controller": "Handles login request, manages session",
      "service": "Authenticates user, decrypts DB data for session storage",
      "dao": "Returns encrypted data from DB"
    }
  },
  "modification_instructions": [
    {
      "file_name": "AuthService.java",
      "target_method": "authenticate",
      "action": "DECRYPT",
      "reason": "FLOW_001: DB data is encrypted, must decrypt before storing plaintext in session",
      "target_columns": [
        {"column_name": "userNm", "policy_id": "P017"},
        {"column_name": "birthDt", "policy_id": "P018"}
      ],
      "insertion_point": "Right after userDao.selectByLoginId() return, before session.setAttribute()",
      "data_object_name": "userInfo",
      "code_pattern_hint": "userInfo.setUserNm(ksignUtil.ksignDec(\"P017\", userInfo.getUserNm()));\nuserInfo.setBirthDt(ksignUtil.ksignDec(\"P018\", userInfo.getBirthDt()));"
    }
  ]
}
```

---

### Example 7: Session to HTTP Response (No crypto needed)

**Input:**
- Method chain: `ProfileController.getMyProfile()` → retrieves data from Session → returns HTTP response
- Note: No DB access, data comes directly from session

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "User profile is retrieved directly from session and returned to client. Since session already stores plaintext (decrypted during login), NO encryption or decryption is needed.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Profile from Session (No DB)",
        "direction": "SESSION_TO_OUTBOUND",
        "data_source": {
          "type": "SESSION",
          "description": "User profile stored in session (already plaintext)"
        },
        "data_sink": {
          "type": "HTTP_RESPONSE",
          "description": "Return profile to client"
        },
        "path": "Session → ProfileController.getMyProfile() → Client",
        "sensitive_columns": ["user_nm", "birth_dt"],
        "crypto_action": "NONE",
        "crypto_timing": "No encryption/decryption needed - session data is already plaintext"
      }
    ],
    "layer_responsibilities": {
      "controller": "Retrieves session data and returns to client",
      "service": "Not involved",
      "dao": "Not involved (no DB access)"
    }
  },
  "modification_instructions": [
    {
      "file_name": "ProfileController.java",
      "target_method": "getMyProfile",
      "action": "SKIP",
      "reason": "FLOW_001: No DB access. Session data is already plaintext (decrypted during login). No encryption/decryption needed.",
      "target_columns": [],
      "insertion_point": "",
      "data_object_name": "",
      "code_pattern_hint": ""
    }
  ]
}
```

---

### Example 8: UPDATE with WHERE on sensitive column

**Input:**
- SQL: `UPDATE customer SET birth_dt = #{newBirthDt} WHERE cust_nm = #{custNm}`
- Method chain: `CustomerController.updateBirthDt()` → `CustomerService.updateBirthDtByName()` → `CustomerDao.updateBirthDtByName()`

**Output:**
```json
{
  "data_flow_analysis": {
    "overview": "Update customer birthdate by name. Both the WHERE condition (cust_nm) and the SET value (birth_dt) are sensitive columns. Must encrypt both the search parameter and the new value before executing UPDATE.",
    "flows": [
      {
        "flow_id": "FLOW_001",
        "flow_name": "Update BirthDt by Name",
        "direction": "INBOUND_TO_DB",
        "data_source": {
          "type": "HTTP_REQUEST",
          "description": "Client sends name (search) and newBirthDt (update value)"
        },
        "data_sink": {
          "type": "DB",
          "description": "UPDATE customer table"
        },
        "path": "CustomerController.updateBirthDt() → CustomerService.updateBirthDtByName() → CustomerDao.updateBirthDtByName() → DB",
        "sensitive_columns": ["cust_nm", "birth_dt"],
        "crypto_action": "ENCRYPT",
        "crypto_timing": "In Service layer, right before DAO call. Encrypt BOTH search param (cust_nm) and update value (birth_dt)."
      }
    ],
    "layer_responsibilities": {
      "controller": "Receives update request",
      "service": "Encrypts both WHERE param and SET value",
      "dao": "Executes UPDATE with encrypted values"
    }
  },
  "modification_instructions": [
    {
      "file_name": "CustomerService.java",
      "target_method": "updateBirthDtByName",
      "action": "ENCRYPT",
      "reason": "FLOW_001: Both WHERE condition (cust_nm) and SET value (birth_dt) must be encrypted before UPDATE",
      "target_columns": [
        {"column_name": "custNm", "policy_id": "P017"},
        {"column_name": "newBirthDt", "policy_id": "P018"}
      ],
      "insertion_point": "Right before customerDao.updateBirthDtByName() call",
      "data_object_name": "updateParams",
      "code_pattern_hint": "// Encrypt both search param and update value\nupdateParams.setCustNm(ksignUtil.ksignEnc(\"P017\", updateParams.getCustNm()));\nupdateParams.setNewBirthDt(ksignUtil.ksignEnc(\"P018\", updateParams.getNewBirthDt()));"
    }
  ]
}
```

---

## data_flow_analysis Field Details

| Field | Description | Example |
|-------|-------------|---------|
| `overview` | Overview of the entire data flow | "The employee table stores user information..." |
| `flows[].flow_id` | Flow identifier | "FLOW_001", "FLOW_002" |
| `flows[].flow_name` | Flow name (function description) | "Employee Registration", "Employee Retrieval" |
| `flows[].direction` | Data direction | "INBOUND_TO_DB", "DB_TO_OUTBOUND" |
| `flows[].data_source.type` | Data source type | "HTTP_REQUEST", "SESSION", "DB", "EXTERNAL_API" |
| `flows[].data_sink.type` | Data destination type | "DB", "HTTP_RESPONSE", "SESSION", "EXTERNAL_API" |
| `flows[].path` | Call path (expressed with arrows) | "Controller → Service → DAO → DB" |
| `flows[].crypto_action` | Required crypto action | "ENCRYPT", "DECRYPT", "NONE" |
| `flows[].crypto_timing` | Encryption/decryption timing | "In Service layer, right before DAO call" |
| `layer_responsibilities` | Role description for each layer | {"controller": "...", "service": "...", "dao": "..."} |

---

## Start Analysis Now

Based on the information above, **analyze the Data Flow first**, then output modification instructions for each file in JSON format based on that analysis.

**Important**: `data_flow_analysis` is the analysis result of the overall data flow, and `modification_instructions` are specific code modification instructions based on that analysis. Clearly distinguish the roles of these two sections.
