import os
from git import Repo
import sys
from app.services.treesitter import Treesitter, LanguageEnum
from collections import defaultdict
from typing import List, Dict
from tree_sitter import Node
from tree_sitter_languages import get_language, get_parser

BLACKLIST_DIR = [
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".git",
    ".idea",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    ".vscode",
    ".github",
    ".gitlab",
    ".angular",
    "cdk.out",
    ".aws-sam",
    ".terraform"
]
WHITELIST_FILES = [".java", ".py", ".js", ".rs"]
BLACKLIST_FILES = ["docker-compose.yml"]


def clone_repository(repo_url):
    """Clones a GitHub repository to a temporary directory.

    Args:
        repo_url: The URL of the GitHub repository.

    Returns:
        The path to the cloned repository.
    """
    repo_name = repo_url.split("/")[-1]  # Extract repository name from URL
    repo_path = f"../../content/{repo_name}"
    Repo.clone_from(repo_url, str(repo_path))
    return str(repo_path)

# def get_file_content(file_path, repo_path):
#     """
#     Get content of a single file.

#     Args:
#         file_path (str): Path to the file

#     Returns:
#         Optional[Dict[str, str]]: Dictionary with file name and content
#     """
#     try:
#         with open(file_path, 'r', encoding='utf-8') as f:
#             content = f.read()

#         # Get relative path from repo root
#         rel_path = os.path.relpath(file_path, repo_path)

#         return {
#             "name": rel_path,
#             "content": content
#         }
#     except Exception as e:
#         print(f"Error processing file {file_path}: {str(e)}")
#         return None


# def get_main_files_content(repo_path: str):
#     """
#     Get content of supported code files from the local repository.

#     Args:
#         repo_path: Path to the local repository

#     Returns:
#         List of dictionaries containing file names and contents
#     """
#     files_content = []

#     try:
#         for root, _, files in os.walk(repo_path):
#             # Skip if current directory is in ignored directories
#             if any(ignored_dir in root for ignored_dir in BLACKLIST_DIR):
#                 continue

#             # Process each file in current directory
#             for file in files:
#                 file_path = os.path.join(root, file)
#                 if os.path.splitext(file)[1] in WHITELIST_FILES:
#                     file_content = get_file_content(file_path, repo_path)
#                     if file_content:
#                         files_content.append(file_content)

#     except Exception as e:
#         print(f"Error reading repository: {str(e)}")

#     return files_content

def get_language_from_extension(file_ext):
    FILE_EXTENSION_LANGUAGE_MAP = {
        ".java": LanguageEnum.JAVA,
        ".py": LanguageEnum.PYTHON,
        ".js": LanguageEnum.JAVASCRIPT,
        ".rs": LanguageEnum.RUST,
        # Add other extensions and languages as needed
    }
    return FILE_EXTENSION_LANGUAGE_MAP.get(file_ext)

def load_files(codebase_path):
    file_list = []
    for root, dirs, files in os.walk(codebase_path):
        dirs[:] = [d for d in dirs if d not in BLACKLIST_DIR]
        for file in files:
            file_ext = os.path.splitext(file)[1]
            if file_ext in WHITELIST_FILES:
                if file not in BLACKLIST_FILES:
                    file_path = os.path.join(root, file)
                    language = get_language_from_extension(file_ext)
                    if language:
                        file_list.append((file_path, language))
                    else:
                        print(f"Unsupported file extension {file_ext} in file {file_path}. Skipping.")
    return file_list

def parse_code_files(file_list):
    class_data = []
    method_data = []

    all_class_names = set()
    all_method_names = set()

    files_by_language = defaultdict(list)
    for file_path, language in file_list:
        files_by_language[language].append(file_path)

    for language, files in files_by_language.items():
        treesitter_parser = Treesitter.create_treesitter(language)
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as file:
                code = file.read()
                file_bytes = code.encode()
                class_nodes, method_nodes = treesitter_parser.parse(file_bytes)

                # Process class nodes
                for class_node in class_nodes:
                    class_name = class_node.name
                    all_class_names.add(class_name)
                    class_data.append({
                        "file_path": file_path,
                        "class_name": class_name,
                        "constructor_declaration": "",  # Extract if needed
                        "method_declarations": "\n-----\n".join(class_node.method_declarations) if class_node.method_declarations else "",
                        "source_code": class_node.source_code,
                        "references": []  # Will populate later
                    })

                # Process method nodes
                for method_node in method_nodes:
                    method_name = method_node.name
                    all_method_names.add(method_name)
                    method_data.append({
                        "file_path": file_path,
                        "class_name": method_node.class_name if method_node.class_name else "",
                        "name": method_name,
                        "doc_comment": method_node.doc_comment,
                        "source_code": method_node.method_source_code,
                        "references": []  # Will populate later
                    })

    return class_data, method_data, all_class_names, all_method_names

def find_references(file_list, class_names, method_names):
    references = {'class': defaultdict(list), 'method': defaultdict(list)}
    files_by_language = defaultdict(list)

    # Convert names to sets for O(1) lookup
    class_names = set(class_names)
    method_names = set(method_names)

    for file_path, language in file_list:
        files_by_language[language].append(file_path)

    for language, files in files_by_language.items():
        treesitter_parser = Treesitter.create_treesitter(language)
        for file_path in files:
            with open(file_path, "r", encoding="utf-8") as file:
                code = file.read()
                file_bytes = code.encode()
                tree = treesitter_parser.parser.parse(file_bytes)

                # Single pass through the AST
                stack = [(tree.root_node, None)]
                while stack:
                    node, parent = stack.pop()

                    # Check for identifiers
                    if node.type == 'identifier':
                        name = node.text.decode()

                        # Check if it's a class reference
                        if name in class_names and parent and parent.type in ['type', 'class_type', 'object_creation_expression']:
                            references['class'][name].append({
                                "file": file_path,
                                "line": node.start_point[0] + 1,
                                "column": node.start_point[1] + 1,
                                "text": parent.text.decode()
                            })

                        # Check if it's a method reference
                        if name in method_names and parent and parent.type in ['call_expression', 'method_invocation']:
                            references['method'][name].append({
                                "file": file_path,
                                "line": node.start_point[0] + 1,
                                "column": node.start_point[1] + 1,
                                "text": parent.text.decode()
                            })

                    # Add children to stack with their parent
                    stack.extend((child, node) for child in node.children)

    return references

def process_repository(repo_url: str):
    codebase_path = clone_repository(repo_url)
    files = load_files(codebase_path)
    class_data, method_data, class_names, method_names = parse_code_files(files)
    references = find_references(files, class_names, method_names)
    class_data_dict = {cd['class_name']: cd for cd in class_data}
    method_data_dict = {(md['class_name'], md['name']): md for md in method_data}

    for class_name, refs in references['class'].items():
        if class_name in class_data_dict:
            class_data_dict[class_name]['references'] = refs

    for method_name, refs in references['method'].items():
        # Find all methods with this name (since methods might have the same name in different classes)
        for key in method_data_dict:
            if key[1] == method_name:
                method_data_dict[key]['references'] = refs

    # Convert dictionaries back to lists
    class_data = list(class_data_dict.values())
    method_data = list(method_data_dict.values())

    return repo_url, codebase_path, references, class_data, method_data




# def create_output_directory(codebase_path):
    normalized_path = os.path.normpath(os.path.abspath(codebase_path))
    codebase_folder_name = os.path.basename(normalized_path)
    output_directory = os.path.join("processed", codebase_folder_name)
    os.makedirs(output_directory, exist_ok=True)
    return output_directory

# def write_class_data_to_csv(class_data, output_directory):
#     output_file = os.path.join(output_directory, "class_data.csv")
#     fieldnames = ["file_path", "class_name", "constructor_declaration", "method_declarations", "source_code", "references"]
#     with open(output_file, "w", newline="", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=fieldnames)
#         writer.writeheader()
#         for row in class_data:
#             references = row.get("references", [])
#             row["references"] = "; ".join([f"{ref['file']}:{ref['line']}:{ref['column']}" for ref in references])
#             writer.writerow(row)
#     print(f"Class data written to {output_file}")

# def write_method_data_to_csv(method_data, output_directory):
#     output_file = os.path.join(output_directory, "method_data.csv")
#     fieldnames = ["file_path", "class_name", "name", "doc_comment", "source_code", "references"]
#     with open(output_file, "w", newline="", encoding="utf-8") as file:
#         writer = csv.DictWriter(file, fieldnames=fieldnames)
#         writer.writeheader()
#         for row in method_data:
#             references = row.get("references", [])
#             row["references"] = "; ".join([f"{ref['file']}:{ref['line']}:{ref['column']}" for ref in references])
#             writer.writerow(row)
#     print(f"Method data written to {output_file}")

# if __name__ == "__main__":
#     if len(sys.argv) < 2:
#         print("Please provide the codebase path as an argument.")
#         sys.exit(1)
#     codebase_path = sys.argv[1]

#     files = load_files(codebase_path)
#     class_data, method_data, class_names, method_names = parse_code_files(files)

#     # Find references
#     references = find_references(files, class_names, method_names)

#     # Map references back to class and method data
#     class_data_dict = {cd['class_name']: cd for cd in class_data}
#     method_data_dict = {(md['class_name'], md['name']): md for md in method_data}

#     for class_name, refs in references['class'].items():
#         if class_name in class_data_dict:
#             class_data_dict[class_name]['references'] = refs

#     for method_name, refs in references['method'].items():
#         # Find all methods with this name (since methods might have the same name in different classes)
#         for key in method_data_dict:
#             if key[1] == method_name:
#                 method_data_dict[key]['references'] = refs

#     # Convert dictionaries back to lists
#     class_data = list(class_data_dict.values())
#     method_data = list(method_data_dict.values())

#     output_directory = create_output_directory(codebase_path)
#     write_class_data_to_csv(class_data, output_directory)
#     write_method_data_to_csv(method_data, output_directory)
