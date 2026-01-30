# Mapper XML Modification Planning (Phase 2)

## Role

You are an expert in analyzing ResultMap and TypeHandler requirements in a Java Spring Boot system.

I will provide you with XML source files and relevant VOs.
**Important**: Your role is **analysis and planning**. Actual code writing will be done in the next step.

Certain columns in the target table require encryption/decryption logic which is currently unimplemented. Your task is to ensure the appropriate TypeHandler is attached to the ResultMap. If a ResultMap is not defined, you must define it correctly.

## Analysis Target Information

### ★★★ Target Table/Column Information (CRITICAL) ★★★

**IMPORTANT: Focus ONLY on the target table specified below.**

This is the specific table that requires encryption/decryption modifications.

{{ table_info }}

**table_info.columns Structure:**

Each column in `table_info.columns` may contain:
- `name`: Column name (always present)
- `new_column`: Whether this is a new column (boolean)
- `column_type`: Type of sensitive data - `"name"`, `"dob"`, or `"rrn"` (optional but authoritative)
- `encryption_code`: Direct policy_id to use - e.g., `"P017"` (optional but highest priority)

**Example:**
```json
{
  "table_name": "TB_BANNER",
  "columns": [
    { "name": "gvnm", "new_column": false, "column_type": "name", "encryption_code": "P017" }
  ]
}
```

**Instructions:**

1. **ALL columns in table_info.columns ARE encryption targets** - do NOT skip any of them.
2. Use `encryption_code` or `column_type` to determine the correct `policy_id`.
3. Analyze queries from `mapping_info.queries[]` (NOT raw SQL - SQL was analyzed in Phase 1).
4. Only analyze methods that are part of call chains in `call_stacks`.
5. Generate modification instructions ONLY for files in `source_files`.

**IMPORTANT: SQL queries are NOT provided directly in this phase.**
Use `mapping_info` from Phase 1 which contains pre-analyzed query information including:
- `query_id`: Which query is being called
- `command_type`: SELECT/INSERT/UPDATE/DELETE
- `crypto_fields`: Which fields need encryption/decryption with their Java field names

### Data Mapping Summary (★ Pre-analyzed from Phase 1)

The following `mapping_info` was extracted in Phase 1 and contains all SQL query analysis results.

**Key Fields to Use:**

| Field | Description | How to Use |
|-------|-------------|------------|
| `query_id` | Matches DAO/Mapper method name | Match with call chain to identify which query is called |
| `command_type` | SQL command type | `SELECT` → DECRYPT results, `INSERT/UPDATE` → ENCRYPT inputs |
| `sql_summary` | Query purpose description | Understand what the query does |
| `crypto_fields` | Array of fields needing encryption | Contains `column_name`, `java_field`, and optional `getter/setter` |
| `java_field` | Field name (VO) or Map key | Use for code generation (e.g., `vo.getJavaField()` or `map.get("java_field")`) |
| `getter/setter` | Methods for VO types (optional) | Use directly in code_pattern_hint; **only present when VO file was provided in Phase 1** |

**Strategy**

### Strategy: Input vs Output Mapping

Data mapping falls into two categories, each requiring a specific modification strategy:

1. **Input Mapping (`input_mapping`) - Encryption for Incoming Data**
   - **Context**: Occurs when data acts as input for a query (e.g., parameters in a `WHERE` clause or values in `INSERT`/`UPDATE`). The data must be encrypted *before* the database operation.
   - **Action**: Modify the SQL parameter placeholder to apply the TypeHandler inline.
   - **Example**: Change `#{myName}` to `#{myName, typeHandler=com.example.typehandler.KsignIDNamValTypeHandler}`.

2. **Output Mapping (`output_mapping`) - Decryption for Return Data**
   - **Context**: Occurs when data is returned from a `SELECT` query. The data must be decrypted properly before reaching upstream layers (Service, Controller).
   - **Action**: Ensure the query maps to a `<resultMap>` and attach the TypeHandler to the specific `<result>` tag.
   - **Example**: 
     ```xml
     <result property="myName" column="MY_NAME" typeHandler="com.example.typehandler.KsignIDNamValTypeHandler" />
     ```

### Source Files to Modify

{{ source_files }}

---

## Analysis Guidelines

### TypeHandler Prerequisite
TypeHandlers are pre-defined in the context. You must select the appropriate TypeHandler from the following list based on the column type:

- **Date of Birth (DOB)**: `KsignIDBirValTypeHandler`
- **Name**: `KsignIDNamValTypeHandler`
- **Resident Registration Number (RRN)**: `KsignIDRrnValTypeHandler`

Check the target column type and choose the appropriate TypeHandler.

### Guidelines
1. **Check for ResultMap**: Determine if a ResultMap needs to be defined. Check if an existing ResultMap is already defined for the VO used by the query requiring encryption.
2. **Define ResultMap**: If a ResultMap needs to be defined, provide instructions on how to define it. Include a code example as a hint.

   **Example:**
   ```xml
   <resultMap id="exampleMap" type="com.example.code.ExampleDaoModel">
       <result property='name' column="NAME" />
       <!-- Example of attaching a TypeHandler -->
       <result property='column_to_enc' column="COLUMN_TO_ENC" typeHandler="com.example.typehandler.KsignIDNamValTypeHandler" />
   </resultMap>
   ```
   *Note: All property and column maps for the result should be provided.*

3. **Modify SQL Query**: If a column needs to be encrypted but the ResultMap is not mapped in the query, provide instructions to modify the SQL query to use the ResultMap.

## Output Format

Provide a comprehensive plan for the execution agent, detailing how to modify the input files to support encryption/decryption.

### 1. Context Summary
Briefly summarize the goal of the modifications for the current task (e.g., "Applying TypeHandler for NAME column in EmployeeMapper").

### 2. Modification Details
List each required modification using the structured format below. Ensure the `code example` shows the **complete, final state** of the XML block.

### Modification [N]
- **file_name**: "example_mapper.xml"
- **target_point**: description of the target code block (e.g., `sql query for <update id="updateEmployeeName">`)
- **target_properties**: list of affected properties (e.g., `["name"]`)
- **reason**: specific reason for the change (e.g., "Input mapping encryption for column 'NAME' in WHERE clause")
- **code example**:
  ```xml
  <update id="updateEmployeeName" parameterType="com.example.vo.EmployeeVO">
      UPDATE TB_EMPLOYEE
      SET EMAIL = #{email}
      WHERE NAME = #{name, typeHandler=com.example.typehandler.KsignIDNamValTypeHandler}
  </update>
  ```

---

**Now, generate the Modification Planning**