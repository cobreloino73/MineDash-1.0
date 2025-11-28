import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useAuth } from './contexts/AuthContext';
import { useNavigate, useLocation } from 'react-router-dom';
import ThinkingProcess from './components/ThinkingProcess';
import Dashboard from './components/Dashboard';
import Insights from './components/Insights';
import FileUpload from './components/FileUpload';
import Sidebar from './components/Sidebar';
// import IGM from './components/IGM'; // ELIMINADO - no se pidió
import {
  Menu,
  Send,
  BarChart3,
  Users,
  Sparkles,
  ArrowRight,
  Search,
  Zap
} from 'lucide-react';

const API_URL = window.location.hostname === 'localhost' ? 'http://localhost:8001' : '';

// Función para streaming SSE
const streamChat = async (query, area, userId, callbacks) => {
  const { onToolStart, onToolResult, onTool, onStatus, onText, onFile, onDone, onError } = callbacks;

  try {
    const response = await fetch(`${API_URL}/api/agent/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream'
      },
      body: JSON.stringify({
        query: query,
        area: area,
        use_lightrag: false,
        user_id: userId
      })
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));

            switch (data.type) {
              case 'status':
                onStatus?.(data.content);
                break;
              case 'tool_start':
                onToolStart?.(data.name, data.description, data.params);
                break;
              case 'tool_result':
                onToolResult?.(data.name, data.success, data.summary);
                break;
              case 'tool':
                onTool?.(data.name, data.content);
                break;
              case 'file':
                onFile?.(data.path);
                break;
              case 'text':
                onText?.(data.content);
                break;
              case 'done':
                onDone?.(data);
                break;
              case 'error':
                onError?.(data.content);
                break;
            }
          } catch (parseError) {
            console.error('Error parsing SSE:', parseError);
          }
        }
      }
    }
  } catch (error) {
    onError?.(error.message);
  }
};

const AREAS = [
  { id: 'todas', name: 'Todas las Áreas', color: '#9c6644' },
  { id: 'carguio', name: 'Carguío', color: '#9c6644' },
  { id: 'transporte', name: 'Transporte', color: '#ea580c' },
  { id: 'perforacion', name: 'Perforación & Tronadura', color: '#c2410c' },
  { id: 'servicios', name: 'Servicios', color: '#3b82f6' },
  { id: 'seguridad', name: 'Seguridad & RRHH', color: '#1e293b' },
  { id: 'costos', name: 'Costos', color: '#1e293b' },
];

const TEMAS_OPERACIONALES = [
  {
    id: 'ranking',
    icon: '🏆',
    titulo: 'Ranking Operadores',
    desc: 'Desempeño y métricas clave',
    query: 'Ranking'
  },
  {
    id: 'match',
    icon: '🔄',
    titulo: 'Match Pala-Camión',
    desc: 'Optimización de asignación',
    query: 'Analiza el match pala-camión y proporciona recomendaciones de asignación óptima'
  },
  {
    id: 'tendencia',
    icon: '📉',
    titulo: 'Tendencia Cumplimiento',
    desc: 'Análisis histórico vs Plan',
    query: 'Muéstrame la tendencia de cumplimiento de los últimos 6 meses'
  },
  {
    id: 'causal',
    icon: '🔍',
    titulo: 'Análisis Causal',
    desc: 'Investigación de desviaciones',
    query: 'Analiza las causas raíz del déficit de cumplimiento usando ASARCO'
  },
  {
    id: 'gaviota',
    icon: '🦅',
    titulo: 'Análisis Gaviota',
    desc: 'Patrones horarios de producción',
    query: 'Muéstrame el análisis de gaviota del 15 de julio 2024 turno A'
  },
  {
    id: 'costos',
    icon: '💰',
    titulo: 'Costos Operacionales',
    desc: 'Eficiencia y oportunidades',
    query: 'Analiza los costos operacionales y oportunidades de mejora'
  }
];

export default function MineDashAI() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [currentView, setCurrentView] = useState('chat');
  // Sidebar cerrado por defecto en móvil (< 768px)
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth >= 768;
    }
    return false;
  });
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [selectedArea, setSelectedArea] = useState('todas');
  const [projects, setProjects] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);
  const [backendConnected, setBackendConnected] = useState(false);
  const [currentToolsUsed, setCurrentToolsUsed] = useState([]);
  const [uploadedFiles, setUploadedFiles] = useState([]);
  const [expandedImage, setExpandedImage] = useState(null);
  const [activeContext, setActiveContext] = useState(null); // Tema activo destacado

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Detectar ruta actual y setear currentView apropiadamente
  useEffect(() => {
    if (location.pathname === '/dashboard') {
      setCurrentView('dashboard');
    } else if (location.pathname === '/alerts') {
      setCurrentView('alertas');
    } else {
      setCurrentView('chat');
    }
  }, [location.pathname]);

  useEffect(() => {
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      const response = await fetch(`${API_URL}/health`);
      setBackendConnected(response.ok);
    } catch (error) {
      setBackendConnected(false);
    }
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Handler para cerrar modal con ESC
  useEffect(() => {
    const handleEsc = (e) => {
      if (e.key === 'Escape' && expandedImage) {
        setExpandedImage(null);
      }
    };

    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [expandedImage]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    // Construir mensaje con contexto si está activo
    let finalMessage = inputMessage;
    if (activeContext) {
      finalMessage = `[CONTEXTO: ${activeContext.label}] ${inputMessage}`;
    }

    const userMessage = {
      role: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString(),
      context: activeContext
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);
    setCurrentToolsUsed([]);

    // Variables para acumular durante streaming
    let accumulatedText = '';
    let accumulatedFiles = [];
    let toolsUsed = [];

    await streamChat(
      finalMessage,
      selectedArea,
      user?.email || 'anonymous',
      {
        onStatus: (status) => {
          // Actualizar estado visual
          setCurrentToolsUsed(prev => {
            const lastTool = prev[prev.length - 1];
            if (lastTool && lastTool.status === 'running') {
              return prev;
            }
            return [...prev, { name: 'status', description: status, status: 'running' }];
          });
        },

        onToolStart: (name, description, params) => {
          const newTool = { name, description: description || `Ejecutando ${name}...`, status: 'running', params };
          toolsUsed.push(newTool);
          setCurrentToolsUsed(prev => [...prev.filter(t => t.status !== 'running' || t.name !== 'status'), newTool]);
        },

        onToolResult: (name, success, summary) => {
          setCurrentToolsUsed(prev =>
            prev.map(tool =>
              tool.name === name && tool.status === 'running'
                ? { ...tool, status: success ? 'success' : 'error', summary }
                : tool
            )
          );
          // Actualizar en toolsUsed para el mensaje final
          toolsUsed = toolsUsed.map(tool =>
            tool.name === name ? { ...tool, status: success ? 'success' : 'error', summary } : tool
          );
        },

        onFile: (path) => {
          accumulatedFiles.push(path);
        },

        // FIX CRITICO: Capturar FINAL_ANSWER del backend
        onTool: (name, content) => {
          if (name === 'FINAL_ANSWER' && content) {
            accumulatedText = content;
          }
        },

        onText: (chunk) => {
          accumulatedText += chunk;
        },

        onDone: (data) => {
          const aiMessage = {
            role: 'assistant',
            content: accumulatedText || data?.response || 'Consulta completada.',
            timestamp: new Date().toISOString(),
            sources: data?.sources || [],
            tools_used: toolsUsed.filter(t => t.name !== 'status'),
            files_generated: accumulatedFiles
          };

          setMessages(prev => [...prev, aiMessage]);
          setIsLoading(false);
          // Limpiar tools después de un momento
          setTimeout(() => setCurrentToolsUsed([]), 500);
        },

        onError: (error) => {
          console.error('Streaming error:', error);

          // Categorizar el error para dar mejor feedback
          let errorMessage = '';
          let errorSuggestion = '';

          if (error.includes('fetch') || error.includes('network') || error.includes('Failed to fetch')) {
            errorMessage = 'No se pudo conectar con el servidor';
            errorSuggestion = 'Verifica que el backend esté corriendo en localhost:8001';
          } else if (error.includes('timeout') || error.includes('Timeout')) {
            errorMessage = 'La consulta tardó demasiado tiempo';
            errorSuggestion = 'Intenta con una consulta más específica o un período más corto';
          } else if (error.includes('500') || error.includes('Internal Server')) {
            errorMessage = 'Error interno del servidor';
            errorSuggestion = 'El equipo técnico ha sido notificado. Intenta nuevamente en unos minutos';
          } else if (error.includes('404')) {
            errorMessage = 'Recurso no encontrado';
            errorSuggestion = 'El endpoint solicitado no existe';
          } else if (error.includes('401') || error.includes('403') || error.includes('Unauthorized')) {
            errorMessage = 'Error de autenticación';
            errorSuggestion = 'Tu sesión puede haber expirado. Intenta cerrar sesión y volver a iniciar';
          } else if (error.includes('rate') || error.includes('limit')) {
            errorMessage = 'Límite de consultas alcanzado';
            errorSuggestion = 'Espera unos segundos antes de hacer otra consulta';
          } else {
            errorMessage = 'Ocurrió un error inesperado';
            errorSuggestion = 'Por favor intenta reformular tu consulta';
          }

          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `⚠️ **${errorMessage}**\n\n💡 *Sugerencia:* ${errorSuggestion}\n\n<details>\n<summary>🔧 Detalles técnicos</summary>\n\n\`${error}\`\n</details>`,
            timestamp: new Date().toISOString(),
            isError: true
          }]);
          setIsLoading(false);
          setCurrentToolsUsed([]);
        }
      }
    );
  };

  const handleNewChat = () => {
    if (messages.length > 0) {
      const newChatHistory = {
        id: Date.now(),
        title: messages[0].content.substring(0, 50) + '...',
        date: new Date().toLocaleDateString('es-CL'),
        messages: messages.length,
        timestamp: new Date().toISOString()
      };
      setChatHistory(prev => [newChatHistory, ...prev]);
    }

    setMessages([]);
    setInputMessage('');
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleTopicClick = (query, temaObj = null) => {
    // NO llenar el input, solo mostrar el badge
    setInputMessage('');

    // Activar contexto visual si es un tema específico
    if (temaObj) {
      setActiveContext({
        label: temaObj.titulo,
        icon: temaObj.icon,
        query: query
      });
    }

    // Enfocar el input para que el usuario escriba
    if (inputRef.current) inputRef.current.focus();
  };

  const loadChatFromHistory = (chatId) => {
    console.log('Cargando chat:', chatId);
  };

  const renderMessage = (text) => {
    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          img: ({node, ...props}) => (
            <img
              {...props}
              onClick={() => setExpandedImage(props.src)}
              style={{
                maxWidth: '100%',
                height: 'auto',
                borderRadius: '8px',
                marginTop: '16px',
                marginBottom: '16px',
                boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                cursor: 'pointer',
                transition: 'transform 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.transform = 'scale(1.02)'}
              onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
              alt={props.alt || 'Imagen'}
            />
          ),
          // Renderizar links a graficos HTML como iframes embebidos
          a: ({node, href, children, ...props}) => {
            // Detectar si es un link a un grafico HTML de outputs/charts
            const isChartLink = href && (
              href.includes('/outputs/charts/') && href.endsWith('.html')
            );

            if (isChartLink) {
              return (
                <div className="my-4 rounded-xl overflow-hidden border border-slate-200 shadow-lg bg-white">
                  <div className="bg-slate-100 px-4 py-2 flex items-center justify-between border-b border-slate-200">
                    <span className="text-sm font-medium text-slate-600 flex items-center gap-2">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                      </svg>
                      Grafico Interactivo
                    </span>
                    <a
                      href={href}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-copper-600 hover:text-copper-800 font-medium"
                    >
                      Abrir en nueva ventana
                    </a>
                  </div>
                  <iframe
                    src={href}
                    title="Grafico"
                    className="w-full border-0"
                    style={{ height: '500px', minHeight: '400px' }}
                    sandbox="allow-scripts allow-same-origin"
                  />
                </div>
              );
            }

            // Links normales
            return (
              <a
                href={href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-copper-600 hover:text-copper-800 underline"
                {...props}
              >
                {children}
              </a>
            );
          },
          code: ({node, inline, ...props}) => {
            // Si es código inline (backticks simples)
            if (inline) {
              return <code className="bg-slate-100 px-1.5 py-0.5 rounded text-sm font-mono text-slate-800" {...props} />;
            }
            // Si es bloque de código (triple backticks o indentado)
            return (
              <pre className="bg-slate-900 text-slate-100 p-4 rounded-lg overflow-x-auto my-4 font-mono text-sm">
                <code {...props} />
              </pre>
            );
          }
        }}
      >
        {text}
      </ReactMarkdown>
    );
  };

  return (
    <div className="min-h-screen w-full flex bg-copper-50/50 font-sans text-slate-800 overflow-hidden">

      {/* BACKGROUND AMBIENT LIGHTING */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] bg-copper-200/30 rounded-full blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[40%] h-[40%] bg-blue-100/30 rounded-full blur-[120px]" />
      </div>

      {/* SIDEBAR COMPONENT */}
      <Sidebar
        sidebarOpen={sidebarOpen}
        setSidebarOpen={setSidebarOpen}
        currentView={currentView}
        setCurrentView={setCurrentView}
        handleNewChat={handleNewChat}
        projects={projects}
        chatHistory={chatHistory}
        loadChatFromHistory={loadChatFromHistory}
        user={user}
        handleLogout={handleLogout}
      />

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 flex flex-col h-screen relative z-10 transition-all duration-300">

        {/* HEADER */}
        <header className="bg-white/70 backdrop-blur-md border-b border-white/50 px-3 sm:px-4 md:px-6 py-3 sm:py-4 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-4">
            {/* Botón hamburguesa - solo visible en móvil */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="md:hidden p-2 hover:bg-white rounded-xl transition-all text-slate-500 hover:text-copper-600 shadow-sm hover:shadow"
            >
              <Menu size={20} />
            </button>

            {currentView === 'dashboard' && (
              <div className="flex items-center gap-2 flex-wrap">
                {AREAS.map(area => (
                  <button
                    key={area.id}
                    onClick={() => setSelectedArea(area.id)}
                    className={`flex items-center gap-2 px-4 py-1.5 rounded-full transition-all font-medium text-xs tracking-wide ${selectedArea === area.id
                        ? 'bg-copper-500 text-white shadow-md shadow-copper-500/20'
                        : 'bg-white text-slate-500 hover:bg-copper-50 hover:text-copper-600 border border-slate-100'
                      }`}
                  >
                    <span>{area.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="flex items-center gap-3">
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full border ${backendConnected
                ? 'bg-green-50 border-green-100 text-green-700'
                : 'bg-red-50 border-red-100 text-red-700'
              }`}>
              <div className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
              <span className="text-xs font-semibold">
                {backendConnected ? 'System Online' : 'System Offline'}
              </span>
            </div>
          </div>
        </header>

        {/* CONTENT BODY */}
        <main className="flex-1 overflow-hidden relative">

          {currentView === 'chat' && (
            <div className="h-full flex flex-col">

              {messages.length === 0 ? (
                // ========== WELCOME SCREEN ==========
                <div className="flex-1 flex flex-col items-center justify-center px-2 sm:px-4 md:px-6 py-4 sm:py-6 md:py-8 overflow-y-auto custom-scrollbar">
                  <div className="max-w-5xl w-full space-y-6 sm:space-y-8 md:space-y-12">

                    {/* Hero Section */}
                    <div className="text-center space-y-6 animate-fade-in-up">
                      <div className="inline-flex items-center justify-center p-4 bg-white rounded-3xl shadow-glass mb-4">
                        <img
                          src="/Logo_Naranja_Codelco.jpg"
                          alt="MineDash AI"
                          className="h-16 w-auto object-contain"
                        />
                      </div>
                      <h1 className="text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-display font-bold text-slate-900 tracking-tight">
                        MineDash <span className="text-transparent bg-clip-text bg-gradient-to-r from-copper-500 to-copper-700">AI</span>
                      </h1>
                      <p className="text-base sm:text-lg md:text-xl text-slate-500 max-w-2xl mx-auto font-light leading-relaxed px-2 sm:px-0">
                        Asistente ejecutivo avanzado para la toma de decisiones estratégicas en operaciones mineras.
                      </p>
                    </div>

                    {/* Search/Input Area */}
                    <div className="w-full max-w-3xl mx-auto relative z-20 px-2 sm:px-4 md:px-0">
                      <div className="glass-input rounded-2xl p-2 transition-all duration-300 focus-within:ring-2 focus-within:ring-copper-500/20 focus-within:shadow-glow">

                        {/* Badge de contexto activo sobre el input (pantalla bienvenida) */}
                        {activeContext && (
                          <div className="flex items-center justify-between px-2 pt-2 pb-1">
                            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-copper-500 text-white rounded-lg text-sm font-semibold shadow-md">
                              <span className="text-lg">{activeContext.icon}</span>
                              <span>{activeContext.label}</span>
                            </div>
                            <button
                              onClick={() => setActiveContext(null)}
                              className="text-xs text-slate-400 hover:text-copper-600 transition-colors px-2 py-1 rounded hover:bg-copper-50"
                              title="Limpiar contexto"
                            >
                              ✕ Limpiar
                            </button>
                          </div>
                        )}

                        <div className="flex items-end gap-2">
                          <div className="pb-2 pl-2">
                            <FileUpload
                              onFileUploaded={(data) => {
                                setUploadedFiles(prev => [...prev, data]);
                                const fileMessage = data.role === 'admin'
                                  ? `📚 Archivo agregado al RAG global: ${data.filename}`
                                  : `📎 Archivo cargado para esta sesión: ${data.filename}`;
                                setMessages(prev => [...prev, { role: 'system', content: fileMessage }]);
                              }}
                            />
                          </div>
                          <textarea
                            ref={inputRef}
                            value={inputMessage}
                            onChange={(e) => setInputMessage(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="¿Qué análisis estratégico necesitas hoy?"
                            className="flex-1 bg-transparent border-none outline-none resize-none text-slate-700 placeholder-slate-400 min-h-[50px] sm:min-h-[60px] py-3 sm:py-4 px-2 text-base sm:text-lg"
                            rows={1}
                            disabled={isLoading || !backendConnected}
                            autoFocus
                          />
                          <button
                            onClick={handleSendMessage}
                            disabled={!inputMessage.trim() || isLoading || !backendConnected}
                            className={`m-2 p-3 rounded-xl transition-all duration-300 ${inputMessage.trim() && !isLoading && backendConnected
                                ? 'bg-copper-500 hover:bg-copper-600 text-white shadow-lg hover:shadow-copper-500/30 transform hover:scale-105'
                                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                              }`}
                          >
                            <ArrowRight size={24} />
                          </button>
                        </div>

                        {/* Uploaded Files Pills */}
                        {uploadedFiles.length > 0 && (
                          <div className="px-4 pb-3 flex flex-wrap gap-2">
                            {uploadedFiles.map((file, idx) => (
                              <div key={idx} className="text-xs px-3 py-1 rounded-full bg-copper-50 text-copper-700 border border-copper-100 flex items-center gap-1">
                                <span>{file.role === 'admin' ? '📚' : '📎'}</span>
                                <span className="font-medium">{file.filename}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>

                      <div className="text-center mt-3 sm:mt-4 hidden sm:flex items-center justify-center gap-3 sm:gap-6 text-xs sm:text-sm text-slate-400 font-medium flex-wrap">
                        <span className="flex items-center gap-1.5"><Sparkles size={14} className="text-copper-500" /> GPT-5.1 Powered</span>
                        <span className="flex items-center gap-1.5"><Zap size={14} className="text-copper-500" /> Real-time</span>
                        <span className="flex items-center gap-1.5"><Search size={14} className="text-copper-500" /> RAG</span>
                      </div>
                    </div>

                    {/* Operational Topics Grid */}
                    <div className="max-w-5xl mx-auto px-2 sm:px-4">
                      <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-6 text-center">Análisis Sugeridos</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {TEMAS_OPERACIONALES.map(tema => (
                          <button
                            key={tema.id}
                            onClick={() => handleTopicClick(tema.query, tema)}
                            className="group glass-card p-5 rounded-2xl hover:bg-white/90 transition-all duration-300 text-left border border-white/40 hover:border-copper-200 hover:shadow-xl hover:-translate-y-1"
                            disabled={isLoading || !backendConnected}
                          >
                            <div className="flex items-start gap-4">
                              <div className="text-3xl bg-copper-50 w-12 h-12 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform duration-300 shadow-sm">
                                {tema.icon}
                              </div>
                              <div>
                                <h3 className="font-bold text-slate-800 group-hover:text-copper-700 transition-colors">
                                  {tema.titulo}
                                </h3>
                                <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                                  {tema.desc}
                                </p>
                              </div>
                            </div>
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                // ========== ACTIVE CHAT ==========
                <>
                  <div className="flex-1 overflow-y-auto px-2 sm:px-4 py-4 sm:py-6 pb-44 sm:pb-56 custom-scrollbar scroll-smooth">
                    <div className="max-w-4xl mx-auto space-y-4 sm:space-y-6 md:space-y-8">
                      {messages.map((msg, idx) => (
                        <div
                          key={idx}
                          className={`flex gap-2 sm:gap-4 md:gap-5 ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}
                        >
                          {msg.role === 'assistant' && (
                            <div className="hidden sm:flex w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-br from-copper-500 to-copper-600 rounded-xl sm:rounded-2xl items-center justify-center flex-shrink-0 shadow-lg shadow-copper-500/20 mt-1">
                              <BarChart3 className="text-white" size={18} />
                            </div>
                          )}

                          <div className={`max-w-[90%] sm:max-w-[85%] md:max-w-3xl relative group ${msg.role === 'user'
                              ? 'bg-gradient-to-br from-copper-500 to-copper-600 text-white rounded-2xl rounded-tr-sm shadow-lg shadow-copper-500/20'
                              : 'glass-card rounded-2xl rounded-tl-sm text-slate-800'
                            } px-4 sm:px-6 md:px-8 py-4 sm:py-5 md:py-6`}>

                            {msg.role === 'assistant' && msg.tools_used && msg.tools_used.length > 0 && (
                              <ThinkingProcess
                                toolsUsed={msg.tools_used}
                                isThinking={false}
                              />
                            )}

                            {/* Badge de contexto activo */}
                            {msg.context && (
                              <div className="mb-3 flex items-center gap-2">
                                <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-copper-100 text-copper-700 rounded-lg text-xs font-semibold border border-copper-200 shadow-sm">
                                  <span className="text-base">{msg.context.icon}</span>
                                  <span>{msg.context.label}</span>
                                </div>
                              </div>
                            )}

                            <div className={`text-sm sm:text-[15px] leading-relaxed markdown-content ${msg.role === 'user' ? 'text-white' : ''}`}>
                              {renderMessage(msg.content)}
                            </div>

                            {msg.sources && msg.sources.length > 0 && (
                              <div className="mt-4 pt-3 border-t border-slate-100 text-xs text-slate-400 flex items-center gap-2">
                                <Search size={12} />
                                <span>Fuentes: {msg.sources.join(', ')}</span>
                              </div>
                            )}

                            {msg.files_generated && msg.files_generated.length > 0 && (
                              <div className="mt-4 pt-3 border-t border-slate-100">
                                <p className="text-xs font-bold text-slate-500 mb-2 uppercase tracking-wider">Archivos Generados</p>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 sm:gap-3">
                                  {msg.files_generated.map((file, i) => {
                                    const isImage = file.match(/\.(png|jpg|jpeg|gif|svg)$/i);
                                    const fileUrl = `${API_URL}${file}`;

                                    return (
                                      <div key={i} className="group/file">
                                        {isImage ? (
                                          <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm hover:shadow-md transition-all">
                                            <img
                                              src={fileUrl}
                                              alt={file.split('/').pop()}
                                              className="w-full h-32 object-cover cursor-pointer"
                                              onClick={() => setExpandedImage(fileUrl)}
                                              title="Click para ampliar"
                                            />
                                            <button
                                              onClick={() => setExpandedImage(fileUrl)}
                                              className="block w-full p-2 text-xs text-center text-copper-600 font-medium bg-copper-50 hover:bg-copper-100 transition-colors"
                                            >
                                              👆 Click para ampliar
                                            </button>
                                          </div>
                                        ) : (
                                          <a
                                            href={fileUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="flex items-center gap-2 p-3 rounded-xl bg-slate-50 hover:bg-copper-50 border border-slate-200 hover:border-copper-200 transition-all text-sm text-slate-600 hover:text-copper-700"
                                          >
                                            <div className="p-2 bg-white rounded-lg shadow-sm">
                                              <Users size={16} />
                                            </div>
                                            <span className="truncate font-medium">{file.split('/').pop()}</span>
                                          </a>
                                        )}
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            )}
                          </div>

                          {msg.role === 'user' && (
                            <div className="hidden sm:flex w-8 h-8 sm:w-10 sm:h-10 bg-white border border-slate-200 rounded-xl sm:rounded-2xl items-center justify-center flex-shrink-0 shadow-sm mt-1">
                              <div className="font-bold text-copper-600 text-sm sm:text-base">
                                {user?.name ? user.name[0] : 'U'}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}

                      {isLoading && (
                        <div className="flex gap-2 sm:gap-4 md:gap-5 justify-start animate-pulse">
                          <div className="hidden sm:flex w-8 h-8 sm:w-10 sm:h-10 bg-gradient-to-br from-copper-500 to-copper-600 rounded-xl sm:rounded-2xl items-center justify-center flex-shrink-0 shadow-lg shadow-copper-500/20">
                            <BarChart3 className="text-white" size={18} />
                          </div>
                          <div className="flex-1 max-w-[90%] sm:max-w-[85%] md:max-w-3xl">
                            <ThinkingProcess
                              toolsUsed={currentToolsUsed}
                              isThinking={true}
                            />
                          </div>
                        </div>
                      )}

                      <div ref={messagesEndRef} className="h-4" />
                    </div>
                  </div>

                  {/* FLOATING INPUT BAR */}
                  <div className="absolute bottom-4 sm:bottom-6 md:bottom-8 left-0 right-0 px-2 sm:px-4 z-30">
                    <div className="w-full max-w-3xl mx-auto">
                      <div className="glass-input rounded-xl sm:rounded-2xl p-1.5 sm:p-2 flex flex-col gap-1 sm:gap-2 shadow-2xl shadow-copper-900/10 ring-1 ring-white/50">

                        {/* Badge de contexto activo sobre el input */}
                        {activeContext && (
                          <div className="flex items-center justify-between px-1.5 sm:px-2 pt-1">
                            <div className="inline-flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1 sm:py-1.5 bg-copper-500 text-white rounded-lg text-xs sm:text-sm font-semibold shadow-md">
                              <span className="text-base sm:text-lg">{activeContext.icon}</span>
                              <span className="truncate max-w-[120px] sm:max-w-none">{activeContext.label}</span>
                            </div>
                            <button
                              onClick={() => setActiveContext(null)}
                              className="text-xs text-slate-400 hover:text-copper-600 transition-colors px-1.5 sm:px-2 py-1 rounded hover:bg-copper-50"
                              title="Limpiar contexto"
                            >
                              ✕
                            </button>
                          </div>
                        )}

                        <div className="flex items-end gap-1 sm:gap-2">
                          <div className="pb-1.5 sm:pb-2 pl-1 sm:pl-2 hidden sm:block">
                            {/* Reusing FileUpload component logic here if needed, or keep it simple */}
                            <button className="p-1.5 sm:p-2 text-slate-400 hover:text-copper-600 transition-colors rounded-lg hover:bg-copper-50">
                              <Search size={18} />
                            </button>
                          </div>
                          <textarea
                          ref={inputRef}
                          value={inputMessage}
                          onChange={(e) => setInputMessage(e.target.value)}
                          onKeyPress={handleKeyPress}
                          placeholder="Escribe tu consulta..."
                          className="flex-1 bg-transparent border-none outline-none resize-none text-slate-700 placeholder-slate-400 max-h-24 sm:max-h-32 py-2 sm:py-3 px-2 text-sm sm:text-base"
                          rows={1}
                          disabled={isLoading || !backendConnected}
                        />
                          <button
                            onClick={handleSendMessage}
                            disabled={!inputMessage.trim() || isLoading || !backendConnected}
                            className={`m-0.5 sm:m-1 p-2.5 sm:p-3 rounded-lg sm:rounded-xl transition-all duration-300 ${inputMessage.trim() && !isLoading && backendConnected
                                ? 'bg-copper-500 hover:bg-copper-600 text-white shadow-lg hover:shadow-copper-500/30'
                                : 'bg-slate-100 text-slate-400 cursor-not-allowed'
                              }`}
                          >
                            <Send size={16} className="sm:w-[18px] sm:h-[18px]" />
                          </button>
                        </div>
                      </div>
                      <p className="text-[9px] sm:text-[10px] text-slate-400 text-center mt-2 sm:mt-3 font-medium tracking-wide uppercase hidden sm:block">
                        {backendConnected
                          ? 'AI-Powered Decision Support System • Codelco Salvador'
                          : '⚠️ Sistema Desconectado'}
                      </p>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}

          {currentView === 'dashboard' && <Dashboard selectedArea={selectedArea} />}
          {currentView === 'alertas' && <Insights />}

        </main>
      </div>

      {/* IMAGE MODAL */}
      {expandedImage && (
        <div
          className="fixed inset-0 bg-black bg-opacity-95 z-[9999] flex items-center justify-center p-8"
          onClick={() => setExpandedImage(null)}
          style={{ cursor: 'zoom-out' }}
        >
          <div className="relative max-w-[95vw] max-h-[95vh] flex items-center justify-center">
            <button
              className="absolute -top-12 right-0 bg-copper-500 hover:bg-copper-600 text-white rounded-lg px-4 py-2 font-bold text-lg shadow-lg transition-all"
              onClick={(e) => {
                e.stopPropagation();
                setExpandedImage(null);
              }}
            >
              ✕ Cerrar
            </button>
            <img
              src={expandedImage}
              alt="Imagen ampliada"
              className="max-w-full max-h-[90vh] object-contain rounded-lg shadow-2xl"
              onClick={(e) => e.stopPropagation()}
            />
            <div className="absolute -bottom-12 left-1/2 transform -translate-x-1/2 text-white text-sm bg-black bg-opacity-75 px-4 py-2 rounded-lg">
              Click fuera de la imagen o presiona ESC para cerrar
            </div>
          </div>
        </div>
      )}

      {/* CSS INJECTION FOR MARKDOWN STYLES */}
      <style jsx>{`
        .markdown-content h1 { font-size: 1.5em; font-weight: 700; color: #1e293b; margin-top: 1em; margin-bottom: 0.5em; letter-spacing: -0.02em; }
        .markdown-content h2 { font-size: 1.25em; font-weight: 600; color: #334155; margin-top: 1em; margin-bottom: 0.5em; }
        .markdown-content h3 { font-size: 1.1em; font-weight: 600; color: #475569; margin-top: 1em; margin-bottom: 0.5em; }
        .markdown-content p { margin-bottom: 0.8em; line-height: 1.7; }
        .markdown-content ul, .markdown-content ol { margin-bottom: 0.8em; padding-left: 1.5em; }
        .markdown-content li { margin-bottom: 0.3em; }
        .markdown-content strong { font-weight: 600; color: #9c6644; }
        .markdown-content code { background: #f1f5f9; padding: 0.2em 0.4em; rounded: 0.3em; font-size: 0.9em; color: #0f172a; font-family: monospace; }
        .markdown-content pre { background: #1e293b; padding: 1em; rounded: 0.5em; overflow-x: auto; color: #f8fafc; margin-bottom: 1em; }
        .markdown-content pre code { background: transparent; color: inherit; padding: 0; }
        .markdown-content blockquote { border-left: 4px solid #9c6644; padding-left: 1em; color: #64748b; font-style: italic; margin-bottom: 1em; }

        .markdown-content table { width: 100%; border-collapse: separate; border-spacing: 0; margin: 1.5em 0; font-size: 0.9em; border-radius: 0.5em; overflow: hidden; border: 1px solid #e2e8f0; }
        .markdown-content th { background: #f8fafc; padding: 0.75em 1em; text-align: left; font-weight: 600; color: #475569; border-bottom: 1px solid #e2e8f0; }
        .markdown-content td { padding: 0.75em 1em; border-bottom: 1px solid #e2e8f0; color: #334155; }
        .markdown-content tr:last-child td { border-bottom: none; }
        .markdown-content tr:hover td { background: #fdf8f6; }
      `}</style>
    </div>
  );
}