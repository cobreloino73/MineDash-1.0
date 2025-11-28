import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import FeedbackButtons from './FeedbackButtons';
import PlotlyChart from '../PlotlyChart';

const ChatMessage = ({ message }) => {
  const isUser = message.role === 'user';
  const [expandedImage, setExpandedImage] = useState(null);

  // Debug: log cuando cambia el estado del modal
  React.useEffect(() => {
    if (expandedImage) {
      console.log('🖼️ Modal DEBE estar visible. Imagen:', expandedImage);
    } else {
      console.log('❌ Modal cerrado');
    }
  }, [expandedImage]);

  // Función para procesar el contenido y detectar imágenes
  const processContent = (content) => {
    // Regex para detectar paths de imágenes backend/outputs/...png o outputs/...png
    const imagePathRegex = /((?:backend\/)?outputs\/[^\s)]+\.(?:png|jpg|jpeg|gif))/g;

    // Reemplazar paths planos con sintaxis markdown de imágenes
    let processedContent = content.replace(imagePathRegex, (match) => {
      // Extraer solo el nombre del archivo (última parte del path)
      const filename = match.split('/').pop();

      // Usar el endpoint /api/image/ que busca automáticamente en subdirectorios
      const imageUrl = `http://localhost:8001/api/image/${filename}`;

      // Retornar sintaxis markdown
      return `\n\n![Gráfico generado](${imageUrl})\n\n`;
    });

    return processedContent;
  };

  return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'}`}>
      <div className="message-avatar">
        {isUser ? '👤' : '🤖'}
      </div>

      <div className="message-content">
        <div className="message-header">
          <span className="message-role">
            {isUser ? 'Tú' : 'MineDash AI'}
          </span>
          <span className="message-time">
            {message.timestamp.toLocaleTimeString('es-CL', {
              hour: '2-digit',
              minute: '2-digit'
            })}
          </span>
        </div>

        <div className="message-text">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              img: ({node, ...props}) => {
                const handleImageClick = (e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  console.log('=== IMAGEN CLICKEADA ===');
                  console.log('URL:', props.src);
                  console.log('Abriendo modal...');
                  setExpandedImage(props.src);
                  console.log('Estado expandedImage actualizado a:', props.src);
                };

                return (
                  <img
                    {...props}
                    style={{
                      maxWidth: '100%',
                      height: 'auto',
                      borderRadius: '8px',
                      marginTop: '16px',
                      marginBottom: '16px',
                      boxShadow: '0 4px 6px rgba(0,0,0,0.1)',
                      cursor: 'pointer',
                      transition: 'transform 0.2s',
                      userSelect: 'none'
                    }}
                    alt={props.alt || 'Imagen'}
                    onClick={handleImageClick}
                    onMouseEnter={(e) => e.target.style.transform = 'scale(1.02)'}
                    onMouseLeave={(e) => e.target.style.transform = 'scale(1)'}
                    onError={(e) => {
                      console.error('Error cargando imagen:', props.src);
                      e.target.style.display = 'none';
                    }}
                  />
                );
              },
              table: ({node, ...props}) => (
                <div style={{ overflowX: 'auto', marginTop: '16px', marginBottom: '16px' }}>
                  <table {...props} style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    border: '1px solid #ddd'
                  }} />
                </div>
              ),
              th: ({node, ...props}) => (
                <th {...props} style={{
                  border: '1px solid #ddd',
                  padding: '12px',
                  backgroundColor: '#f2f2f2',
                  fontWeight: 'bold',
                  textAlign: 'left'
                }} />
              ),
              td: ({node, ...props}) => (
                <td {...props} style={{
                  border: '1px solid #ddd',
                  padding: '12px',
                  textAlign: 'left'
                }} />
              )
            }}
          >
            {processContent(message.content)}
          </ReactMarkdown>
        </div>

        {/* Gráfico Plotly interactivo (si existe) */}
        {message.chart && (
          <PlotlyChart chart={message.chart} height={500} />
        )}

        {/* Archivos generados */}
        {message.files && message.files.length > 0 && (
          <div className="message-files">
            {message.files.map((file, index) => (
              <a
                key={index}
                href={`http://localhost:8001${file}`}
                target="_blank"
                rel="noopener noreferrer"
                className="file-link"
              >
                📊 Ver {file.includes('chart') ? 'gráfico' : 'reporte'}
              </a>
            ))}
          </div>
        )}

        {/* Botones de Feedback - Solo para mensajes del asistente */}
        {!isUser && message.interactionId && (
          <FeedbackButtons
            interactionId={message.interactionId}
            messageId={message.id}
          />
        )}
      </div>

      {/* Modal para imagen expandida - Portal style overlay */}
      {expandedImage && (
        <div
          className="image-modal-overlay"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            width: '100vw',
            height: '100vh',
            backgroundColor: 'rgba(0, 0, 0, 0.95)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 999999,
            cursor: 'pointer',
            padding: '2rem'
          }}
          onClick={() => {
            console.log('Modal cerrado - overlay click');
            setExpandedImage(null);
          }}
        >
          <div
            style={{
              position: 'relative',
              maxWidth: '95vw',
              maxHeight: '95vh',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={expandedImage}
              alt="Imagen expandida"
              style={{
                maxWidth: '100%',
                maxHeight: '95vh',
                objectFit: 'contain',
                borderRadius: '8px',
                boxShadow: '0 10px 40px rgba(0,0,0,0.5)'
              }}
            />
            <button
              style={{
                position: 'absolute',
                top: '-50px',
                right: '-10px',
                backgroundColor: '#f97316',
                border: 'none',
                color: 'white',
                fontSize: '24px',
                cursor: 'pointer',
                padding: '8px 16px',
                borderRadius: '8px',
                fontWeight: 'bold',
                boxShadow: '0 4px 12px rgba(249, 115, 22, 0.3)',
                transition: 'all 0.2s'
              }}
              onClick={(e) => {
                e.stopPropagation();
                console.log('Botón cerrar clickeado');
                setExpandedImage(null);
              }}
              onMouseEnter={(e) => e.target.style.backgroundColor = '#ea580c'}
              onMouseLeave={(e) => e.target.style.backgroundColor = '#f97316'}
            >
              ✕ Cerrar
            </button>
            <div
              style={{
                position: 'absolute',
                bottom: '-50px',
                left: '50%',
                transform: 'translateX(-50%)',
                color: '#a1a1aa',
                fontSize: '14px',
                textAlign: 'center'
              }}
            >
              Haz clic fuera de la imagen o presiona el botón para cerrar
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatMessage;