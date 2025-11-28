import React, { useState, useEffect, useRef } from 'react';
import WelcomeScreen from './WelcomeScreen';
import ChatMessage from './ChatMessage';
import ChatInput from './ChatInput';
import ProcessPanel from './ProcessPanel';
import { agentChatStream } from '../../services/api';
import '../../styles/chat.css';

const ChatContainer = () => {
  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [processSteps, setProcessSteps] = useState([]);
  const [streamingText, setStreamingText] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll al ultimo mensaje
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingText, processSteps]);

  const handleSendMessage = async (text) => {
    if (!text.trim()) return;

    // Agregar mensaje del usuario
    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: text,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsLoading(true);
    setProcessSteps([]);
    setStreamingText('');

    // Variables para acumular datos durante streaming
    let accumulatedText = '';
    let accumulatedFiles = [];
    let accumulatedChart = null;
    let interactionId = null;

    try {
      await agentChatStream(
        text,
        {
          // Status: Mensajes de estado general
          onStatus: (status) => {
            setProcessSteps(prev => {
              // Si ya hay un paso pendiente, actualizar; si no, agregar
              const lastStep = prev[prev.length - 1];
              if (lastStep && lastStep.status === 'pending') {
                return [...prev.slice(0, -1), { ...lastStep, description: status, status: 'running' }];
              }
              return [...prev, { description: status, status: 'running' }];
            });
          },

          // Tool Start: Herramienta iniciando
          onToolStart: (name, description, params) => {
            setProcessSteps(prev => [
              ...prev,
              {
                name,
                description: description || `Ejecutando ${name}...`,
                status: 'running',
                params
              }
            ]);
          },

          // Tool Result: Herramienta completada
          onToolResult: (name, success, summary) => {
            setProcessSteps(prev =>
              prev.map(step =>
                step.name === name && step.status === 'running'
                  ? { ...step, status: success ? 'success' : 'error', summary }
                  : step
              )
            );
          },

          // Tool: Contenido completo de herramienta (FINAL_ANSWER)
          onTool: (name, content) => {
            // FINAL_ANSWER contiene la respuesta estructurada
            if (name === 'FINAL_ANSWER' && content) {
              try {
                const parsed = JSON.parse(content);
                if (parsed.answer) {
                  accumulatedText = parsed.answer;
                  setStreamingText(parsed.answer);
                }
                // Capturar chart si viene en la respuesta
                if (parsed.chart) {
                  accumulatedChart = parsed.chart;
                }
              } catch {
                // Si no es JSON, usar como texto directo
                accumulatedText = content;
                setStreamingText(content);
              }
            }
          },

          // Chart: Gráfico interactivo generado
          onChart: (chartData) => {
            accumulatedChart = chartData;
          },

          // File: Archivo generado
          onFile: (path) => {
            accumulatedFiles.push(path);
          },

          // Text: Chunk de texto (streaming palabra por palabra)
          onText: (chunk) => {
            accumulatedText += chunk;
            setStreamingText(accumulatedText);
          },

          // Done: Finalizacion
          onDone: (data) => {
            interactionId = data?.interaction_id;

            // Capturar chart de data.chart si existe
            if (data?.chart) {
              accumulatedChart = data.chart;
            }

            // Crear mensaje final del asistente
            const assistantMessage = {
              id: Date.now() + 1,
              role: 'assistant',
              content: accumulatedText || data?.response || 'Consulta completada.',
              files: accumulatedFiles,
              chart: accumulatedChart,  // Gráfico interactivo Plotly
              interactionId: interactionId,
              timestamp: new Date()
            };

            setMessages(prev => [...prev, assistantMessage]);
            setStreamingText('');
            setIsLoading(false);

            // Marcar todos los pasos como completados
            setProcessSteps(prev =>
              prev.map(step => ({
                ...step,
                status: step.status === 'running' ? 'success' : step.status
              }))
            );

            if (data?.conversation_id) {
              setConversationId(data.conversation_id);
            }
          },

          // Error: Error en el proceso
          onError: (error) => {
            console.error('Streaming error:', error);

            const errorMessage = {
              id: Date.now() + 1,
              role: 'assistant',
              content: `Error al procesar la consulta: ${error}`,
              timestamp: new Date()
            };

            setMessages(prev => [...prev, errorMessage]);
            setStreamingText('');
            setIsLoading(false);

            setProcessSteps(prev =>
              prev.map(step => ({
                ...step,
                status: step.status === 'running' ? 'error' : step.status
              }))
            );
          }
        },
        true, // useAI
        'anonymous' // userId
      );

    } catch (error) {
      console.error('Error:', error);

      const errorMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Error al procesar la consulta. Por favor intenta nuevamente.',
        timestamp: new Date()
      };

      setMessages(prev => [...prev, errorMessage]);
      setIsLoading(false);
      setStreamingText('');
    }
  };

  // Determinar si mostrar welcome screen o chat
  const showWelcome = messages.length === 0;

  return (
    <div className="chat-container">
      {showWelcome ? (
        <WelcomeScreen
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
        />
      ) : (
        <div className="chat-active">
          <div className="chat-messages">
            {messages.map(message => (
              <ChatMessage
                key={message.id}
                message={message}
              />
            ))}

            {/* Panel de proceso durante streaming */}
            {isLoading && processSteps.length > 0 && (
              <div className="chat-message assistant">
                <div className="message-avatar">🤖</div>
                <div className="message-content">
                  <ProcessPanel
                    steps={processSteps}
                    isProcessing={isLoading}
                  />

                  {/* Texto en streaming */}
                  {streamingText && (
                    <div className="message-text streaming">
                      {streamingText}
                      <span className="cursor-blink">|</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Indicador de carga simple cuando no hay pasos */}
            {isLoading && processSteps.length === 0 && (
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-container">
            <ChatInput
              onSendMessage={handleSendMessage}
              disabled={isLoading}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatContainer;
