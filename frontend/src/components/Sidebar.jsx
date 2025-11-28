import React from 'react';
import {
    MessageSquare,
    LayoutDashboard,
    Bell,
    Plus,
    FolderOpen,
    Clock,
    LogOut,
    Settings,
    ChevronLeft,
    BarChart3
} from 'lucide-react';

const Sidebar = ({
    sidebarOpen,
    setSidebarOpen,
    currentView,
    setCurrentView,
    handleNewChat,
    projects = [],
    chatHistory = [],
    loadChatFromHistory,
    user,
    handleLogout
}) => {
    return (
        <>
            {/* Overlay para cerrar sidebar en móvil */}
            {sidebarOpen && (
                <div
                    className="fixed inset-0 bg-black/50 z-40 md:hidden"
                    onClick={() => setSidebarOpen(false)}
                />
            )}

            <div
                className={`
                    fixed inset-y-0 left-0 z-50 w-72
                    transform transition-transform duration-300 ease-in-out
                    ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
                    md:translate-x-0 md:relative md:z-30
                    flex flex-col bg-white/95 md:bg-white/80 backdrop-blur-xl border-r border-white/20 shadow-lg md:shadow-glass
                `}
            >
            {/* Header / Logo */}
            <div className="p-4 sm:p-6 border-b border-copper-100/50">
                {/* Botón cerrar - solo móvil */}
                <button
                    onClick={() => setSidebarOpen(false)}
                    className="md:hidden absolute top-3 right-3 p-2 rounded-lg hover:bg-copper-50 text-slate-400 hover:text-copper-600 transition-colors"
                >
                    <ChevronLeft size={20} />
                </button>

                <div className="flex items-center justify-center mb-4">
                    <img
                        src="/Logo_Blanco_Codelco.jpg"
                        alt="Codelco División Salvador"
                        className="w-28 sm:w-32 h-auto object-contain mix-blend-multiply opacity-90 hover:opacity-100 transition-opacity"
                        onError={(e) => {
                            e.target.style.display = 'none';
                        }}
                    />
                </div>
                <div className="text-center">
                    <h1 className="font-display font-bold text-lg sm:text-xl text-slate-900 tracking-tight">MineDash AI</h1>
                    <p className="text-xs text-slate-500 font-medium tracking-wide uppercase mt-1">División Salvador</p>
                </div>
            </div>

            {/* New Chat Button */}
            <div className="p-4">
                <button
                    onClick={handleNewChat}
                    className="w-full group relative overflow-hidden flex items-center justify-center gap-2 bg-gradient-to-r from-copper-600 to-copper-500 text-white py-3.5 px-4 rounded-xl shadow-lg shadow-copper-500/20 hover:shadow-copper-500/30 transition-all duration-300 transform hover:-translate-y-0.5"
                >
                    <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300" />
                    <Plus size={18} className="relative z-10" />
                    <span className="relative z-10 font-medium">Nueva Conversación</span>
                </button>
            </div>

            {/* Navigation */}
            <nav className="px-3 space-y-1 mb-6">
                {[
                    { id: 'chat', icon: MessageSquare, label: 'Chat Assistant' },
                    { id: 'dashboard', icon: LayoutDashboard, label: 'Operational Dashboard' },
                    { id: 'alertas', icon: Bell, label: 'Smart Alerts' }
                ].map((item) => (
                    <button
                        key={item.id}
                        onClick={() => {
                            setCurrentView(item.id);
                            // Cerrar sidebar en móvil al seleccionar
                            if (window.innerWidth < 768) {
                                setSidebarOpen(false);
                            }
                        }}
                        className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group ${currentView === item.id
                                ? 'bg-copper-50 text-copper-700 shadow-sm font-semibold'
                                : 'text-slate-500 hover:bg-white hover:text-copper-600 hover:shadow-sm'
                            }`}
                    >
                        <item.icon
                            size={20}
                            className={`transition-colors ${currentView === item.id ? 'text-copper-600' : 'text-slate-400 group-hover:text-copper-500'
                                }`}
                        />
                        <span className="font-medium">{item.label}</span>
                    </button>
                ))}
            </nav>

            {/* Scrollable Content */}
            <div className="flex-1 overflow-y-auto px-3 py-2 space-y-6 custom-scrollbar">

                {/* Projects Section */}
                <div>
                    <div className="flex items-center justify-between mb-3 px-2">
                        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider">Proyectos Activos</h3>
                        <button className="text-slate-300 hover:text-copper-600 transition-colors p-1 hover:bg-copper-50 rounded">
                            <Plus size={14} />
                        </button>
                    </div>

                    {projects.length === 0 ? (
                        <div className="px-4 py-4 rounded-lg border border-dashed border-slate-200 text-center">
                            <p className="text-xs text-slate-400">Sin proyectos activos</p>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {projects.map(project => (
                                <button
                                    key={project.id}
                                    className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-white hover:shadow-sm transition-all text-sm text-slate-600 hover:text-copper-700 flex items-center gap-2.5 group"
                                >
                                    <FolderOpen size={16} className="text-slate-300 group-hover:text-copper-500 transition-colors" />
                                    <span className="flex-1 truncate font-medium">{project.name}</span>
                                    <span className="text-[10px] bg-slate-100 text-slate-400 px-1.5 py-0.5 rounded-full group-hover:bg-copper-100 group-hover:text-copper-600 transition-colors">
                                        {project.chatCount}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* History Section */}
                <div>
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3 px-2">Historial Reciente</h3>
                    {chatHistory.length === 0 ? (
                        <div className="px-4 py-8 text-center">
                            <div className="w-8 h-8 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-2">
                                <Clock size={14} className="text-slate-300" />
                            </div>
                            <p className="text-xs text-slate-400">No hay historial</p>
                        </div>
                    ) : (
                        <div className="space-y-1">
                            {chatHistory.map(chat => (
                                <button
                                    key={chat.id}
                                    onClick={() => loadChatFromHistory(chat.id)}
                                    className="w-full text-left px-3 py-2.5 rounded-lg hover:bg-white hover:shadow-sm transition-all text-sm text-slate-600 hover:text-copper-700 group"
                                >
                                    <div className="flex items-start gap-2.5">
                                        <Clock size={14} className="mt-0.5 flex-shrink-0 text-slate-300 group-hover:text-copper-500 transition-colors" />
                                        <div className="flex-1 min-w-0">
                                            <div className="font-medium truncate">{chat.title}</div>
                                            <div className="text-[10px] text-slate-400 mt-0.5 flex items-center gap-1">
                                                <span>{chat.date}</span>
                                                <span>•</span>
                                                <span>{chat.messages} msgs</span>
                                            </div>
                                        </div>
                                    </div>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* User Profile */}
            <div className="p-4 border-t border-copper-100/50 bg-white/50 backdrop-blur-sm">
                <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-white/80 transition-colors cursor-pointer group">
                    <div className="w-10 h-10 bg-gradient-to-br from-copper-500 to-copper-700 rounded-full flex items-center justify-center text-white font-bold shadow-md group-hover:shadow-lg transition-all">
                        {user?.name ? user.name[0] : 'U'}
                    </div>
                    <div className="flex-1 min-w-0">
                        <p className="font-semibold text-sm text-slate-800 truncate">{user?.name || 'Usuario'}</p>
                        <p className="text-xs text-copper-600 font-medium truncate">{user?.company || 'Codelco Chile'}</p>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="text-slate-400 hover:text-red-500 transition-colors p-1.5 hover:bg-red-50 rounded-lg"
                        title="Cerrar sesión"
                    >
                        <LogOut size={18} />
                    </button>
                </div>
            </div>
        </div>
        </>
    );
};

export default Sidebar;
