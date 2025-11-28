import React, { useState } from 'react';
import axios from 'axios';
import { useAuth } from '../contexts/AuthContext';
import { Paperclip, Loader2, ShieldCheck } from 'lucide-react';

const FileUpload = ({ onFileUploaded }) => {
  const { user } = useAuth();
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);

  const isAdmin = user?.role === 'admin';

  const handleFileChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_id', user.email);
    formData.append('user_role', user.role);

    setUploading(true);

    try {
      const response = await axios.post('http://localhost:8001/api/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          setProgress(percentCompleted);
        },
      });

      if (onFileUploaded) {
        onFileUploaded(response.data);
      }

      // Mensaje diferenciado según rol
      const successMessage = isAdmin
        ? `✅ Archivo agregado al RAG global: ${file.name}\nDisponible para todos los usuarios`
        : `✅ Archivo cargado para tu sesión: ${file.name}`;

      alert(successMessage);
    } catch (error) {
      console.error('Error uploading file:', error);
      alert('Error al subir archivo: ' + (error.response?.data?.error || error.message));
    } finally {
      setUploading(false);
      setProgress(0);
      e.target.value = '';
    }
  };

  return (
    <div className="relative group">
      <input
        type="file"
        onChange={handleFileChange}
        className="hidden"
        id="file-upload"
        accept=".xlsx,.xls,.csv,.pdf,.txt,.json"
        disabled={uploading}
      />
      <label
        htmlFor="file-upload"
        className={`cursor-pointer inline-flex items-center justify-center p-3 rounded-xl transition-all duration-300 ${uploading
            ? 'bg-slate-100 text-slate-400 cursor-not-allowed'
            : 'text-slate-500 hover:text-copper-600 hover:bg-copper-50 hover:shadow-sm hover:shadow-copper-500/10'
          }`}
        title={isAdmin ? "Subir archivo al RAG global (Admin)" : "Subir archivo temporal"}
      >
        {uploading ? (
          <Loader2 className="w-5 h-5 animate-spin" />
        ) : (
          <div className="relative">
            <Paperclip className="w-5 h-5 transform group-hover:rotate-12 transition-transform" />
            {isAdmin && (
              <ShieldCheck className="w-3 h-3 absolute -top-1.5 -right-1.5 text-copper-600 bg-white rounded-full" />
            )}
          </div>
        )}
      </label>

      {uploading && (
        <div className="absolute bottom-full mb-3 left-1/2 transform -translate-x-1/2 glass-card bg-white/90 backdrop-blur-md rounded-xl shadow-xl p-3 z-20 min-w-[220px] animate-fade-in-up">
          <div className="flex justify-between items-center mb-2">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
              {isAdmin ? 'Procesando RAG' : 'Subiendo'}
            </span>
            <span className="text-xs font-bold text-copper-600">{progress}%</span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-gradient-to-r from-copper-500 to-copper-400 h-full rounded-full transition-all duration-300 shadow-[0_0_10px_rgba(249,115,22,0.5)]"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default FileUpload;
