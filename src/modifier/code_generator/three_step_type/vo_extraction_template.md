# VO/SQL Field Mapping Extraction (Phase 1)

## Role

You are an expert in analyzing Java VO (Value Object) classes and SQL queries.
Your task is to extract **field mapping information** from the provided VO files and SQL queries.

**Important**:
- This is an **extraction and analysis** task only
- You are NOT modifying any code
- You are providing structured information for the next analysis phase

---

## ★★★ Target Table Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table specified below.**

Many VO files and SQL queries may be provided for context, but you must **ONLY analyze and extract mappings related to the target table**.

{{ table_info }}

**Instructions:**
1. Among all the provided VO files, identify which ones are used for operations on the **target table** above
2. Among all the provided SQL queries, identify which ones access the **target table** above
3. Extract field mappings ONLY for VO classes and SQL queries that are related to the **target table**
4. Ignore VO files and SQL queries that do not interact with the **target table**

---

## Encryption Framework Information (KSign)

This project uses the **KSign** encryption framework. The following are the ONLY fields that require encryption:

### Policy IDs (★ ONLY these 3 field types are encryption targets)
| Field Type | Policy ID | Column Name Patterns |
|------------|-----------|---------------------|
| **Name (이름)** | `"P017"` | name, userName, user_name, fullName, firstName, lastName, custNm, CUST_NM, empNm, EMP_NM, memNm, MEM_NM |
| **Date of Birth (생년월일)** | `"P018"` | dob, dateOfBirth, birthDate, birthday, dayOfBirth, birthDt, BIRTH_DT |
| **Resident Number (주민번호)** | `"P019"` | jumin, juminNumber, ssn, residentNumber, juminNo, JUMIN_NO, residentNo |

**IMPORTANT**: ONLY extract mapping information for Name, DOB, and Jumin fields **that are in the target table's columns**. Ignore all other fields.

---

## VO Files to Analyze

{{ vo_files }}

---

## SQL Queries to Analyze

{{ sql_queries }}

---

## Output Format (Must output in JSON format)

**Important**: This output will be used in Phase 2 for data flow analysis. Include all information needed to:
1. Match call chain methods with SQL queries (via `query_id`)
2. Determine crypto action (via `query_type`: INSERT/UPDATE → ENCRYPT, SELECT → DECRYPT)
3. Generate encryption/decryption code (via `getter`, `setter`, `policy_id`)

```json
{
  "vo_summary": {
    "total_vo_count": <number of VO classes analyzed for target table>,
    "encryption_target_fields_count": <number of fields that need encryption>
  },
  "vo_mappings": [
    {
      "vo_class_name": "ClassName (e.g., EmployeeVO)",
      "vo_file_path": "File path if available",
      "related_table": "Target table name this VO is used for",
      "fields": [
        {
          "field_name": "Java field name in VO (e.g., empNm)",
          "field_type": "Java type (e.g., String)",
          "getter": "Getter method name (e.g., getEmpNm)",
          "setter": "Setter method name (e.g., setEmpNm)",
          "is_encryption_target": true,
          "policy_id": "P017 | P018 | P019",
          "mapped_sql_columns": ["List of SQL column names this field maps to (e.g., emp_nm, EMP_NM)"],
          "mapped_sql_aliases": ["List of SQL aliases this field maps to (e.g., empNm, employeeName)"]
        }
      ]
    }
  ],
  "sql_column_usage": [
    {
      "query_id": "SQL query ID = DAO method name (e.g., selectEmployee, insertUser)",
      "query_type": "SELECT | INSERT | UPDATE | DELETE",
      "encryption_target_columns": ["List of columns that need encryption (only name, dob, jumin)"],
      "column_aliases": {
        "alias_in_query": "actual_column_name"
      },
      "target_vo_class": "VO class that this query uses (for finding getter/setter)"
    }
  ]
}
```

---

## Extraction Guidelines

### 1. VO Field Analysis
For each VO class:
1. Identify all fields (member variables)
2. Extract getter and setter method names
3. Mark fields as `is_encryption_target: true` ONLY if they match name, DOB, or jumin patterns
4. Assign the correct `policy_id` based on field type:
   - Name fields → `"P017"`
   - DOB fields → `"P018"`
   - Jumin fields → `"P019"`

### 2. SQL Column Analysis
For each SQL query:
1. Identify the query type (SELECT/INSERT/UPDATE/DELETE)
2. Extract column names used in the query
3. Note any aliases used (e.g., `emp_nm AS empNm`)
4. Identify which columns are encryption targets

### 3. Field-Column Mapping Rules
Map VO fields to SQL columns using these conventions:
- **Camel Case to Snake Case**: `empNm` → `emp_nm`, `EMP_NM`
- **Aliases in SQL**: `SELECT emp_nm AS empNm` means `empNm` in VO maps to `emp_nm` in DB
- **ResultMap in MyBatis**: Check if there's explicit mapping

### 4. Common Naming Patterns
| VO Field (Java) | SQL Column Patterns |
|-----------------|---------------------|
| `empNm` | `emp_nm`, `EMP_NM`, `empNm` |
| `birthDt` | `birth_dt`, `BIRTH_DT`, `birthDt` |
| `juminNo` | `jumin_no`, `JUMIN_NO`, `juminNo` |
| `custNm` | `cust_nm`, `CUST_NM`, `custNm` |
| `userNm` | `user_nm`, `USER_NM`, `userNm` |
| `memNm` | `mem_nm`, `MEM_NM`, `memNm` |

---

## Example

### Input VO File:
```java
public class EmployeeVO {
    private String empNo;
    private String empNm;      // Name field - encryption target
    private String birthDt;    // DOB field - encryption target
    private String deptCd;
    private String juminNo;    // Jumin field - encryption target

    public String getEmpNm() { return empNm; }
    public void setEmpNm(String empNm) { this.empNm = empNm; }
    public String getBirthDt() { return birthDt; }
    public void setBirthDt(String birthDt) { this.birthDt = birthDt; }
    public String getJuminNo() { return juminNo; }
    public void setJuminNo(String juminNo) { this.juminNo = juminNo; }
    // ... other getters/setters
}
```

### Input SQL Query:
```xml
<select id="selectEmployee" resultType="EmployeeVO">
    SELECT emp_no, emp_nm AS empNm, birth_dt AS birthDt, dept_cd, jumin_no AS juminNo
    FROM employee
    WHERE emp_no = #{empNo}
</select>

<insert id="insertEmployee">
    INSERT INTO employee (emp_no, emp_nm, birth_dt, dept_cd, jumin_no)
    VALUES (#{empNo}, #{empNm}, #{birthDt}, #{deptCd}, #{juminNo})
</insert>
```

### Expected Output:
```json
{
  "vo_summary": {
    "total_vo_count": 1,
    "encryption_target_fields_count": 3
  },
  "vo_mappings": [
    {
      "vo_class_name": "EmployeeVO",
      "vo_file_path": "com/example/vo/EmployeeVO.java",
      "fields": [
        {
          "field_name": "empNm",
          "field_type": "String",
          "getter": "getEmpNm",
          "setter": "setEmpNm",
          "is_encryption_target": true,
          "policy_id": "P017",
          "mapped_sql_columns": ["emp_nm", "EMP_NM"],
          "mapped_sql_aliases": ["empNm"]
        },
        {
          "field_name": "birthDt",
          "field_type": "String",
          "getter": "getBirthDt",
          "setter": "setBirthDt",
          "is_encryption_target": true,
          "policy_id": "P018",
          "mapped_sql_columns": ["birth_dt", "BIRTH_DT"],
          "mapped_sql_aliases": ["birthDt"]
        },
        {
          "field_name": "juminNo",
          "field_type": "String",
          "getter": "getJuminNo",
          "setter": "setJuminNo",
          "is_encryption_target": true,
          "policy_id": "P019",
          "mapped_sql_columns": ["jumin_no", "JUMIN_NO"],
          "mapped_sql_aliases": ["juminNo"]
        }
      ]
    }
  ],
  "sql_column_usage": [
    {
      "query_id": "selectEmployee",
      "query_type": "SELECT",
      "encryption_target_columns": ["emp_nm", "birth_dt", "jumin_no"],
      "column_aliases": {
        "empNm": "emp_nm",
        "birthDt": "birth_dt",
        "juminNo": "jumin_no"
      },
      "target_vo_class": "EmployeeVO"
    },
    {
      "query_id": "insertEmployee",
      "query_type": "INSERT",
      "encryption_target_columns": ["emp_nm", "birth_dt", "jumin_no"],
      "column_aliases": {},
      "target_vo_class": "EmployeeVO"
    }
  ]
}
```

---

## Important Notes

1. **Focus on Target Table ONLY**: Even if many VO files and SQL queries are provided, ONLY extract information related to the **target table** specified in the Target Table Information section
2. **Only extract encryption-related fields**: Focus only on Name (P017), DOB (P018), and Jumin (P019) fields that are in the target table's columns
3. **Be thorough with aliases**: SQL queries often use aliases that differ from column names
4. **Filter relevant VO classes**: Only include VO classes that are used for operations on the target table
5. **Filter relevant SQL queries**: Only include SQL queries that access the target table
6. **Include all naming variants**: For each field, include both camelCase and snake_case variants

---

## Start Extraction Now

Analyze the provided VO files and SQL queries **for the target table only**, then output the field mapping information in the JSON format specified above.

**Remember**: Focus on the target table. Ignore VO classes and SQL queries that do not interact with the target table.
