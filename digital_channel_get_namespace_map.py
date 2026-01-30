import os
import re
import json

CONFIG_FILE = "config.json"
OUTPUT_FILE = "digital_chananel_specific_map.json"

def get_target_project():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("target_project")
    except Exception as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        return None

def find_java_files(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith("Dao.java") or file.endswith("DaoModel.java") or file.endswith("Service.java"):
                yield os.path.join(root, file)

def extract_info(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None, None, None
    
    # Check for NAMESPACE
    # Pattern for: private static final String NAMESPACE = "value";
    # Allow some flexibility
    namespace_match = re.search(r'String\s+NAMESPACE\s*=\s*"([^"]+)"', content)
    
    if not namespace_match:
        return None, None, None

    namespace = namespace_match.group(1).strip().strip('.')
    
    class_name = os.path.basename(file_path).replace(".java", "")
    
    # Extract methods
    # We want to match method declarations. 
    # Typical signature: [modifiers] ReturnType methodName(Args) [throws Exceptions] { ... }
    # OR interface: [modifiers] ReturnType methodName(Args);
    
    methods = []
    
    # Remove strings and comments to avoid false positives (simple approach)
    # This is not perfect but better for regex
    clean_content = re.sub(r'//.*', '', content) # remove single line comments
    clean_content = re.sub(r'/\*.*?\*/', '', clean_content, flags=re.DOTALL) # remove block comments
    clean_content = re.sub(r'"(?:[^"\\]|\\.)*"', '""', clean_content) # remove string literals
    
    # Regex to find method definitions
    # 1. Look for word (return type)
    # 2. Look for word (method name)
    # 3. Look for (
    
    # Naive regex for methods:
    # (public|protected|private|static|\s) + [\w<>\[\]]+ \s+ (\w+) \s* \(
    
    # However, we must ensure it's not a control structure like 'if (', 'for (', 'while ('
    # And we want to support interface methods which might not have modifiers.
    
    # Let's use a regex that looks for an identifier followed by parenthesis, 
    # preceeded by a type.
    
    # Exclude keywords common in flow control
    keywords = {'if', 'while', 'for', 'switch', 'catch', 'synchronized', 'super', 'this'}
    
    # Pattern:
    # (?:modifiers\s+)* (?:<.*?>\s+)? type\s+ name\s*\(
    
    # A simplified pattern that catches most standard Java method declarations:
    # We look for something that looks like a method header.
    # We expect at least one word (return type) before the method name.
    
    # method_pattern = re.compile(r'(?:public|protected|private|static|final|native|synchronized|abstract|transient|\s)+[\w<>\[\]]+\s+(\w+)\s*\(')
    
    # Better approach might be:
    # (\w+) \s* \(
    # Then check if group 1 is a keyword.
    
    # But we need to make sure it is a declaration, not a call.
    # Declarations usually have a type before them.
    # Call: methodName(arg)
    # Declaration: Type methodName(ArgType arg)
    
    # So we look for: Type \s+ Name \s* \(
    
    regex = r'(?:[a-zA-Z0-9_<>\[\]]+)\s+([a-zA-Z0-9_]+)\s*\('
    
    matches = re.finditer(regex, clean_content)
    
    for match in matches:
        name = match.group(1)
        if name in keywords:
            continue
        
        # Filter out constructors (name == class_name)
        if name == class_name:
            continue
            
        # Filter out "new" (e.g. new ArrayList() -> matches ArrayList as type and ( as start of args? no. "new ArrayList (" -> type=new name=ArrayList)
        # Actually our regex requires "Type Name (", so "new ArrayList(" matches Type="new" Name="ArrayList".
        if name == 'new': 
            continue
            
        # Additional cleanup:
        # If it looks like a variable declaration "String str = new ...", usage might not match "Type Name (" unless it is "Type Name("
        
        methods.append(name)

    # De-duplicate
    methods = list(set(methods))
    
    return namespace, class_name, methods

def main():
    target_dir = get_target_project()
    if not target_dir:
        print("Could not find target_project in config.json")
        return

    print(f"Scanning target directory: {target_dir}")
    
    result = {}
    
    count = 0
    for file_path in find_java_files(target_dir):
        # print(f"Checking {file_path}...")
        namespace, class_name, methods = extract_info(file_path)
        if namespace:
            if namespace not in result:
                result[namespace] = {}
            
            result[namespace][class_name] = methods
            count += 1
            print(f"[{count}] Found {class_name} in {namespace} with {len(methods)} methods")

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=4, ensure_ascii=False)
    
    print(f"Saved {count} entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
