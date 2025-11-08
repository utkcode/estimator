"""Configuration constants for the application"""
import os

# Folder paths
PROJECTS_FOLDER = 'projects'
SCOPE_CONFIG_FOLDER = 'scope_config'
DATABASE = 'estimator.db'

# Allowed file extensions
ALLOWED_EXTENSIONS = {'doc', 'docx', 'pdf', 'txt', 'xlsx', 'xls', 'csv'}

# Create necessary directories
for folder in [PROJECTS_FOLDER, SCOPE_CONFIG_FOLDER]:
    os.makedirs(folder, exist_ok=True)

