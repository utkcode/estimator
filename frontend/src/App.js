import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = 'http://localhost:5000/api';

function App() {
  const [projects, setProjects] = useState([]);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showScopeConfigModal, setShowScopeConfigModal] = useState(false);
  const [scopeConfigExists, setScopeConfigExists] = useState(false);
  const [scopeConfigFilename, setScopeConfigFilename] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedProject, setSelectedProject] = useState(null);
  const [contextMenu, setContextMenu] = useState(null);

  const [newProject, setNewProject] = useState({
    name: '',
    file: null
  });

  useEffect(() => {
    fetchProjects();
    checkScopeConfig();
  }, []);

  const fetchProjects = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/projects`);
      const data = await response.json();
      setProjects(data);
    } catch (error) {
      console.error('Error fetching projects:', error);
    }
  };

  const checkScopeConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/scope-config`);
      const data = await response.json();
      setScopeConfigExists(data.exists);
      if (data.exists && data.filename) {
        setScopeConfigFilename(data.filename);
      }
    } catch (error) {
      console.error('Error checking scope config:', error);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    if (!newProject.name || !newProject.file) {
      alert('Please provide project name and upload a document');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('project_name', newProject.name);
    formData.append('file', newProject.file);

    try {
      const response = await fetch(`${API_BASE_URL}/projects`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        const project = await response.json();
        setProjects([...projects, project]);
        setShowCreateModal(false);
        setNewProject({ name: '', file: null });
        alert('Project created successfully!');
      } else {
        const error = await response.json();
        alert(`Error: ${error.error}`);
      }
    } catch (error) {
      console.error('Error creating project:', error);
      alert('Error creating project');
    } finally {
      setLoading(false);
    }
  };

  const handleScopeConfigUpload = async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById('scope-config-file');
    if (!fileInput.files[0]) {
      alert('Please select a file');
      return;
    }

    setLoading(true);
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);

    try {
      const response = await fetch(`${API_BASE_URL}/scope-config`, {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        await response.json();
        setShowScopeConfigModal(false);
        checkScopeConfig();
        alert('Scope config uploaded successfully!');
      } else {
        const error = await response.json();
        alert(`Error: ${error.error}`);
      }
    } catch (error) {
      console.error('Error uploading scope config:', error);
      alert('Error uploading scope config');
    } finally {
      setLoading(false);
    }
  };

  const handleProjectClick = async (projectId) => {
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`);
      const data = await response.json();
      setSelectedProject(data);
    } catch (error) {
      console.error('Error fetching project details:', error);
    }
  };

  const handleDownloadCSV = async (projectId, projectName) => {
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}/download-csv`);
      
      if (!response.ok) {
        const error = await response.json();
        alert(`Error: ${error.error}`);
        return;
      }
      
      // Get the blob and create download link
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${projectName || 'project'}_results.csv`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error('Error downloading CSV:', error);
      alert('Error downloading CSV file');
    }
  };

  const handleProjectRightClick = (e, project) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      project: project
    });
  };

  const handleDeleteProject = async (projectId) => {
    if (!window.confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
      setContextMenu(null);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`, {
        method: 'DELETE'
      });

      if (response.ok) {
        // Remove project from list
        setProjects(projects.filter(p => p.id !== projectId));
        // Close context menu
        setContextMenu(null);
        // If deleted project was selected, clear selection
        if (selectedProject && selectedProject.id === projectId) {
          setSelectedProject(null);
        }
        alert('Project deleted successfully');
      } else {
        const error = await response.json();
        alert(`Error: ${error.error}`);
      }
    } catch (error) {
      console.error('Error deleting project:', error);
      alert('Error deleting project');
    }
  };

  const handleScopeConfigRightClick = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      type: 'scope-config'
    });
  };

  const handleDeleteScopeConfig = async () => {
    if (!window.confirm('Are you sure you want to delete the scope config file? You will need to upload it again to create projects.')) {
      setContextMenu(null);
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/scope-config`, {
        method: 'DELETE'
      });

      if (response.ok) {
        setContextMenu(null);
        checkScopeConfig();
        alert('Scope config deleted successfully');
      } else {
        const error = await response.json();
        alert(`Error: ${error.error}`);
      }
    } catch (error) {
      console.error('Error deleting scope config:', error);
      alert('Error deleting scope config');
    }
  };

  useEffect(() => {
    const handleClickOutside = () => {
      setContextMenu(null);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  return (
    <div className="app-container">
      <div className="main-content">
        <div className="header-section">
          <h1 className="app-title">Project Estimator</h1>
          <div className="button-group">
            <button 
              className="btn btn-primary" 
              onClick={() => setShowCreateModal(true)}
              disabled={!scopeConfigExists}
            >
              New Project
            </button>
            <button 
              className="btn btn-secondary" 
              onClick={() => setShowScopeConfigModal(true)}
            >
              Scope Config
            </button>
          </div>
          {!scopeConfigExists && (
            <p className="warning-text">⚠️ Please upload Scope Config file to create projects</p>
          )}
        </div>

        <div className="projects-section">
          <h2>Projects</h2>
          <div className="projects-list">
            {projects.length === 0 ? (
              <p className="empty-state">No projects yet</p>
            ) : (
              projects.map((project) => (
                <div 
                  key={project.id} 
                  className="project-card"
                  onClick={() => handleProjectClick(project.id)}
                  onContextMenu={(e) => handleProjectRightClick(e, project)}
                >
                  <h3>{project.name}</h3>
                  <p className="project-status">{project.status}</p>
                  <p className="project-date">{new Date(project.created_at).toLocaleDateString()}</p>
                </div>
              ))
            )}
          </div>
        </div>

        {selectedProject && (
          <div className="project-details">
            <button className="close-btn" onClick={() => setSelectedProject(null)}>×</button>
            <h2>{selectedProject.name}</h2>
            <p><strong>Status:</strong> {selectedProject.status}</p>
            <p><strong>Created:</strong> {new Date(selectedProject.created_at).toLocaleString()}</p>
            {selectedProject.results && (
              <div className="results-table">
                <div className="results-header">
                  <h3>Results</h3>
                  <button 
                    className="btn btn-download" 
                    onClick={() => handleDownloadCSV(selectedProject.id, selectedProject.name)}
                  >
                    Download CSV
                  </button>
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Product</th>
                      <th>Features</th>
                      <th>Size</th>
                      <th>Hours</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedProject.results.map((item, index) => (
                      <tr key={index}>
                        <td>{item.product}</td>
                        <td>{item.features}</td>
                        <td>{item.size}</td>
                        <td>{item.hours || item.hours === 0 ? item.hours : 'N/A'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={() => setShowCreateModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Create New Project</h2>
            <form onSubmit={handleCreateProject}>
              <div className="form-group">
                <label>Project Name</label>
                <input
                  type="text"
                  value={newProject.name}
                  onChange={(e) => setNewProject({ ...newProject, name: e.target.value })}
                  required
                />
              </div>
              <div className="form-group">
                <label>Upload Document</label>
                <input
                  type="file"
                  accept=".doc,.docx,.pdf,.txt"
                  onChange={(e) => setNewProject({ ...newProject, file: e.target.files[0] })}
                  required
                />
              </div>
              <div className="modal-buttons">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? 'Creating...' : 'Create'}
                </button>
                <button 
                  type="button" 
                  className="btn btn-cancel" 
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Scope Config Modal */}
      {showScopeConfigModal && (
        <div className="modal-overlay" onClick={() => setShowScopeConfigModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h2>Upload Scope Config</h2>
            <form onSubmit={handleScopeConfigUpload}>
              <div className="form-group">
                <label>Upload Excel/CSV File</label>
                {scopeConfigExists && scopeConfigFilename && (
                  <p 
                    className="current-file-info"
                    onContextMenu={handleScopeConfigRightClick}
                  >
                    Current file: <strong>{scopeConfigFilename}</strong>
                  </p>
                )}
                <input
                  id="scope-config-file"
                  type="file"
                  accept=".xlsx,.xls,.csv"
                  required
                />
              </div>
              <div className="modal-buttons">
                <button type="submit" className="btn btn-primary" disabled={loading}>
                  {loading ? 'Uploading...' : 'Upload'}
                </button>
                <button 
                  type="button" 
                  className="btn btn-cancel" 
                  onClick={() => setShowScopeConfigModal(false)}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Context Menu */}
      {contextMenu && (
        <div 
          className="context-menu"
          style={{
            position: 'fixed',
            left: `${contextMenu.x}px`,
            top: `${contextMenu.y}px`,
            zIndex: 1000
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {contextMenu.type === 'scope-config' ? (
            <button
              className="context-menu-item delete"
              onClick={handleDeleteScopeConfig}
            >
              Delete Scope Config
            </button>
          ) : (
            <button
              className="context-menu-item delete"
              onClick={() => handleDeleteProject(contextMenu.project.id)}
            >
              Delete Project
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
