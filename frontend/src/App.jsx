import React, { useState, useRef, useEffect } from 'react';
import { 
  MessageSquare, 
  LayoutDashboard, 
  Bell,
  Plus, 
  Send, 
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Users,
  Truck,
  HardHat,
  DollarSign,
  BarChart3,
  Menu,
  X,
  FolderOpen,
  Clock
} from 'lucide-react';
import {
  getRankingProduccion,
  getAnalisisCausal,
  sendRAGQuery,
} from './services/api';

const AREAS = [
  { id: 'todas', name: 'Todas las Áreas', icon: LayoutDashboard, color: 'claude-500' },
  { id: 'carguio', name: 'Carguío', icon: Truck, color: 'claude-400' },
  { id: 'transporte', name: 'Transporte', icon: Truck, color: 'claude-500' },
  { id: 'perforacion', name: 'Perforación', icon: HardHat, color: 'claude-600' },
  { id: 'seguridad', name: 'Seguridad & RRHH', icon: Users, color: 'red-500' },
  { id: 'costos', name: 'Costos', icon: DollarSign, color: 'green-500' },
];

const PROYECTOS = [];

function App() {
  const [currentView, setCurrentView] = useState('chat');
  const [selectedArea, setSelectedArea] = useState(AREAS[0]);
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [alertasCount] = useState(3);
  const [chatsHistory, setChatsHistory] = useState([]);
  const [currentChatId, setCurrentChatId] = useState(null);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputMessage.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const query = inputMessage.toLowerCase();
      
      if (query.includes('ranking') || query.includes('top')) {
        const response = await getRankingProduccion(2024, 10);
        const ranking = response.data.ranking;
        
        const assistantMessage = {
          id: Date.now() + 1,
          type: 'assistant',
          content: `📊 **Top 10 Operadores por Producción 2024**\n\n${ranking.map((op, i) => 
            `${i + 1}. **${op.operador}**\n   └─ ${op.toneladas_total_formatted} ton | ${op.dumps} dumps | ${op.ton_por_dump} ton/dump`
          ).join('\n\n')}`,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      } 
      else if (query.includes('barraza') || query.includes('causal') || query.includes('operador')) {
        const apellido = query.match(/\b[A-Z]+\b/)?.[0] || 'BARRAZA';
        const response = await getAnalisisCausal(apellido, 2024);
        const data = response.data;
        
        const assistantMessage = {
          id: Date.now() + 1,
          type: 'assistant',
          content: `🔍 **Análisis Causal: ${data.operador}**\n\n**Producción:**\n- ${data.produccion.total_dumps} dumps\n- ${data.produccion.total_toneladas_formatted} toneladas\n- ${data.produccion.equipos_diferentes} equipos operados\n\n**Utilización:** ${data.utilizacion.utilizacion_pct}%\n⚠️ ${data.interpretacion.join('\n')}\n\n**Top Equipos:**\n${data.top_5_equipos.map(eq => `• ${eq.equipo}: ${eq.toneladas_formatted} ton`).join('\n')}`,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      }
      else {
        const response = await sendRAGQuery(inputMessage, 'hybrid');
        
        const assistantMessage = {
          id: Date.now() + 1,
          type: 'assistant',
          content: response.data.response,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: '❌ Error al procesar la consulta. Verifica que el backend esté corriendo en http://localhost:8000',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleNewChat = () => {
    if (messages.length > 0) {
      const newChat = {
        id: Date.now(),
        title: messages[0].content.substring(0, 50) + (messages[0].content.length > 50 ? '...' : ''),
        date: 'Ahora',
        messages: messages.length
      };
      setChatsHistory(prev => [newChat, ...prev]);
    }
    setMessages([]);
    setCurrentChatId(null);
  };

  const loadChat = (chatId) => {
    setCurrentChatId(chatId);
    alert(`Funcionalidad de carga de chat ${chatId} próximamente`);
  };

  return (
    <div className="flex h-screen bg-warm-50 text-warm-900">
      
      {/* SIDEBAR */}
      <div className={`${sidebarOpen ? 'w-64' : 'w-0'} transition-all duration-300 bg-white border-r border-warm-200 flex flex-col overflow-hidden`}>
        
        <div className="p-4 border-b border-warm-200">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-claude-400 to-claude-600 rounded-lg flex items-center justify-center">
              <BarChart3 className="text-white" size={24} />
            </div>
            <div>
              <h1 className="font-bold text-lg text-warm-900">MineDash AI</h1>
              <p className="text-xs text-warm-500">División Salvador</p>
            </div>
          </div>
        </div>

        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 bg-claude-500 hover:bg-claude-600 text-white py-2 px-4 rounded-lg transition-colors"
          >
            <Plus size={18} />
            <span className="font-medium">Nuevo Chat</span>
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto custom-scrollbar p-3 space-y-1">
          <button
            onClick={() => setCurrentView('chat')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              currentView === 'chat' 
                ? 'bg-claude-50 text-claude-600' 
                : 'hover:bg-warm-100 text-warm-700'
            }`}
          >
            <MessageSquare size={20} />
            <span className="font-medium">Chat</span>
          </button>

          <button
            onClick={() => setCurrentView('dashboard')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              currentView === 'dashboard' 
                ? 'bg-claude-50 text-claude-600' 
                : 'hover:bg-warm-100 text-warm-700'
            }`}
          >
            <LayoutDashboard size={20} />
            <span className="font-medium">Dashboard</span>
          </button>

          <button
            onClick={() => setCurrentView('alertas')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${
              currentView === 'alertas' 
                ? 'bg-claude-50 text-claude-600' 
                : 'hover:bg-warm-100 text-warm-700'
            }`}
          >
            <Bell size={20} />
            <span className="font-medium">Alertas</span>
            {alertasCount > 0 && (
              <span className="ml-auto bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                {alertasCount}
              </span>
            )}
          </button>

          {/* Proyectos */}
          <div className="pt-4">
            <div className="px-3 pb-2 text-xs font-semibold text-warm-500 uppercase tracking-wider">
              Proyectos
            </div>
            {PROYECTOS.length > 0 ? (
              PROYECTOS.map(proyecto => (
                <button
                  key={proyecto.id}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-warm-100 text-warm-700 transition-colors"
                >
                  <FolderOpen size={18} className={`text-${proyecto.color}`} />
                  <div className="flex-1 text-left">
                    <div className="text-sm font-medium">{proyecto.name}</div>
                    <div className="text-xs text-warm-500">{proyecto.chats} chats</div>
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-sm text-warm-500">
                No hay proyectos aún
              </div>
            )}
          </div>

          {/* Historial */}
          <div className="pt-4">
            <div className="px-3 pb-2 text-xs font-semibold text-warm-500 uppercase tracking-wider">
              Historial
            </div>
            {chatsHistory.length > 0 ? (
              chatsHistory.slice(0, 5).map(chat => (
                <button
                  key={chat.id}
                  onClick={() => loadChat(chat.id)}
                  className="w-full flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-warm-100 text-warm-700 transition-colors text-left"
                >
                  <Clock size={16} className="flex-shrink-0" />
                  <div className="flex-1 overflow-hidden">
                    <div className="text-sm truncate">{chat.title}</div>
                    <div className="text-xs text-warm-500">{chat.date}</div>
                  </div>
                </button>
              ))
            ) : (
              <div className="px-3 py-4 text-center text-sm text-warm-500">
                No hay conversaciones previas
              </div>
            )}
          </div>
        </nav>
      </div>

      {/* CONTENIDO PRINCIPAL */}
      <div className="flex-1 flex flex-col">
        
        <div className="bg-white border-b border-warm-200 p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 hover:bg-warm-100 rounded-lg transition-colors"
              >
                {sidebarOpen ? <X size={20} /> : <Menu size={20} />}
              </button>
              
              {currentView === 'dashboard' && (
                <div className="flex items-center gap-2">
                  {AREAS.map(area => (
                    <button
                      key={area.id}
                      onClick={() => setSelectedArea(area)}
                      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                        selectedArea.id === area.id
                          ? `bg-${area.color} text-white`
                          : 'bg-warm-100 text-warm-700 hover:bg-warm-200'
                      }`}
                    >
                      {area.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
            
            <div className="flex items-center gap-3">
              <div className="text-sm text-warm-600">
                🟢 Backend Conectado
              </div>
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar">
          
          {/* VISTA CHAT */}
          {currentView === 'chat' && (
            <div className="flex flex-col h-full">
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {messages.length === 0 ? (
                  <div className="max-w-3xl mx-auto mt-20">
                    <div className="text-center mb-12">
                      <div className="w-20 h-20 bg-gradient-to-br from-claude-400 to-claude-600 rounded-2xl flex items-center justify-center mx-auto mb-6">
                        <BarChart3 className="text-white" size={40} />
                      </div>
                      <h2 className="text-4xl font-bold mb-3 text-warm-900">Hola, David 👋</h2>
                      <p className="text-warm-600 text-lg">¿En qué puedo ayudarte hoy?</p>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      {[
                        { text: "❌ ¿Por qué no cumplimos tonelaje?", query: "Análisis de cumplimiento de tonelaje y causas raíz" },
                        { text: "📊 Análisis de KPIs operacionales", query: "Muestra disponibilidad, utilización y rendimiento" },
                        { text: "⚙️ ¿Qué demoras impactan más?", query: "Análisis de códigos ASARCO con mayor impacto en utilización" },
                        { text: "🏆 Ranking de rendimiento", query: "Muestra el ranking de equipos y operadores por rendimiento" }
                      ].map((suggestion, i) => (
                        <button
                          key={i}
                          onClick={() => setInputMessage(suggestion.query)}
                          className="p-4 bg-white hover:bg-warm-50 rounded-xl text-left transition-colors border border-warm-200"
                        >
                          <div className="font-medium text-warm-900">{suggestion.text}</div>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="max-w-4xl mx-auto space-y-6">
                    {messages.map((msg) => (
                      <div
                        key={msg.id}
                        className={`flex gap-4 ${msg.type === 'user' ? 'flex-row-reverse' : ''} animate-fade-in`}
                      >
                        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${
                          msg.type === 'user' 
                            ? 'bg-warm-200' 
                            : 'bg-gradient-to-br from-claude-400 to-claude-600'
                        }`}>
                          {msg.type === 'user' ? '👤' : '🤖'}
                        </div>
                        <div className={`flex-1 ${msg.type === 'user' ? 'text-right' : ''}`}>
                          <div className={`inline-block p-4 rounded-xl ${
                            msg.type === 'user'
                              ? 'bg-claude-500 text-white'
                              : 'bg-white border border-warm-200 text-warm-900'
                          }`}>
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                    {isLoading && (
                      <div className="flex gap-4">
                        <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-claude-400 to-claude-600 flex items-center justify-center">
                          🤖
                        </div>
                        <div className="flex-1">
                          <div className="inline-block p-4 bg-white border border-warm-200 rounded-xl">
                            <div className="flex gap-2">
                              <div className="w-2 h-2 bg-claude-400 rounded-full animate-bounce"></div>
                              <div className="w-2 h-2 bg-claude-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                              <div className="w-2 h-2 bg-claude-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              <div className="border-t border-warm-200 p-4 bg-white">
                <div className="max-w-4xl mx-auto">
                  <div className="flex gap-3">
                    <input
                      type="text"
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                      placeholder="Pregunta sobre operaciones, rankings, análisis..."
                      className="flex-1 bg-warm-100 text-warm-900 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-claude-500 placeholder-warm-500"
                      disabled={isLoading}
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={isLoading || !inputMessage.trim()}
                      className="bg-claude-500 hover:bg-claude-600 disabled:bg-warm-200 disabled:text-warm-500 text-white px-6 py-3 rounded-lg transition-colors flex items-center gap-2"
                    >
                      <Send size={20} />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* VISTA DASHBOARD */}
          {currentView === 'dashboard' && (
            <div className="p-6 space-y-6">
              <div>
                <h2 className="text-2xl font-bold mb-2 text-warm-900">Dashboard - {selectedArea.name}</h2>
                <p className="text-warm-600">Métricas en tiempo real</p>
              </div>

              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: 'Producción Hoy', value: '12,450 ton', change: '+5.2%', up: true, icon: TrendingUp },
                  { label: 'Disponibilidad', value: '87.3%', change: '+2.1%', up: true, icon: TrendingUp },
                  { label: 'Utilización', value: '76.8%', change: '-1.5%', up: false, icon: TrendingDown },
                  { label: 'Dotación Turno', value: '142/150', change: '-8', up: false, icon: Users },
                ].map((kpi, i) => (
                  <div key={i} className="bg-white rounded-xl p-6 border border-warm-200">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-warm-600">{kpi.label}</span>
                      <kpi.icon size={20} className={kpi.up ? 'text-green-500' : 'text-red-500'} />
                    </div>
                    <div className="text-2xl font-bold mb-1 text-warm-900">{kpi.value}</div>
                    <div className={`text-sm ${kpi.up ? 'text-green-500' : 'text-red-500'}`}>
                      {kpi.change} vs ayer
                    </div>
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="bg-white rounded-xl p-6 border border-warm-200">
                  <h3 className="font-bold text-lg mb-4 text-warm-900">Producción por Turno</h3>
                  <div className="h-64 flex items-center justify-center text-warm-500">
                    📊 Gráfico de barras aquí
                  </div>
                </div>
                <div className="bg-white rounded-xl p-6 border border-warm-200">
                  <h3 className="font-bold text-lg mb-4 text-warm-900">Disponibilidad Equipos</h3>
                  <div className="h-64 flex items-center justify-center text-warm-500">
                    📈 Gráfico de línea aquí
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* VISTA ALERTAS */}
          {currentView === 'alertas' && (
            <div className="p-6 space-y-6">
              <div>
                <h2 className="text-2xl font-bold mb-2 text-warm-900">Alertas Activas</h2>
                <p className="text-warm-600">{alertasCount} alertas requieren atención</p>
              </div>

              <div className="space-y-4">
                {[
                  { tipo: 'critical', titulo: 'Pala P&H 4100 fuera de servicio', descripcion: 'Falla eléctrica mayor. Tiempo estimado reparación: 72 horas.', area: 'Carguío' },
                  { tipo: 'warning', titulo: 'Turno C bajo rendimiento', descripcion: 'Producción 15% bajo promedio últimos 7 días.', area: 'Producción' },
                  { tipo: 'info', titulo: 'Mantención programada mañana', descripcion: '3 camiones CAT en mantención preventiva 06:00-14:00.', area: 'Transporte' }
                ].map((alerta, i) => (
                  <div key={i} className={`p-6 rounded-xl border ${
                    alerta.tipo === 'critical' ? 'bg-red-50 border-red-200' :
                    alerta.tipo === 'warning' ? 'bg-yellow-50 border-yellow-200' :
                    'bg-blue-50 border-blue-200'
                  }`}>
                    <div className="flex items-start gap-4">
                      <AlertTriangle size={24} className={
                        alerta.tipo === 'critical' ? 'text-red-500' :
                        alerta.tipo === 'warning' ? 'text-yellow-500' :
                        'text-blue-500'
                      } />
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="font-bold text-lg text-warm-900">{alerta.titulo}</span>
                          <span className="text-xs px-3 py-1 bg-warm-100 rounded-full text-warm-700">
                            {alerta.area}
                          </span>
                        </div>
                        <p className="text-warm-700 mb-3">{alerta.descripcion}</p>
                        <div className="text-sm text-warm-500">Hace 2 horas</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;