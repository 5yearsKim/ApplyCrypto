import os
import shutil

def copy_templates():
    """
    Copies all template files from src/templates to src/modifier/code_generator.
    Maintains directory structure.
    """
    project_root = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(project_root, 'src', 'templates')
    target_dir = os.path.join(project_root, 'src', 'modifier', 'code_generator')

    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    print(f"Copying templates from '{source_dir}' to '{target_dir}'...")

    copied_count = 0
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            source_file = os.path.join(root, file)
            
            # Calculate relative path to maintain structure
            rel_path = os.path.relpath(root, source_dir)
            
            if rel_path == '.':
                 target_subdir = target_dir
            else:
                 target_subdir = os.path.join(target_dir, rel_path)

            if not os.path.exists(target_subdir):
                os.makedirs(target_subdir)
            
            target_file = os.path.join(target_subdir, file)
            
            try:
                shutil.copy2(source_file, target_file)
                print(f"Copied: {file} -> {target_subdir}")
                copied_count += 1
            except Exception as e:
                print(f"Error copying {file}: {e}")

    print(f"Template initialization complete. {copied_count} files copied.")

if __name__ == "__main__":
    copy_templates()
