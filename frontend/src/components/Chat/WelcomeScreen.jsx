import React, { useState } from 'react';

const WelcomeScreen = ({ onSendMessage, isLoading }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleSuggestionClick = (text) => {
    setInput(text);
  };

  const suggestions = [
    "¿Cuál fue el tonelaje de enero 2025?",
    "Muéstrame el análisis gaviota del 15 de julio turno A",
    "Top 10 operadores por producción",
    "Análisis de utilización de septiembre 2025"
  ];

  return (
    <div className="welcome-screen">
      <div className="welcome-content">
        <div className="welcome-header">
          <div className="logo">⛏️</div>
          <h1>Buenas noches, David</h1>
          <p className="subtitle">MineDash AI - El primer chatbot minero de la historia</p>
        </div>

        <form onSubmit={handleSubmit} className="welcome-input-form">
          <div className="input-wrapper">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="¿Cómo puedo ayudarte hoy?"
              className="welcome-input"
              disabled={isLoading}
              autoFocus
            />
            <button 
              type="submit" 
              className="send-button"
              disabled={!input.trim() || isLoading}
            >
              {isLoading ? '⏳' : '➤'}
            </button>
          </div>
        </form>

        <div className="suggestions">
          <p className="suggestions-title">Prueba preguntar:</p>
          <div className="suggestions-grid">
            {suggestions.map((suggestion, index) => (
              <button
                key={index}
                className="suggestion-chip"
                onClick={() => handleSuggestionClick(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className="welcome-footer">
          <span className="powered-by">Powered by AIMINE</span>
        </div>
      </div>
    </div>
  );
};

export default WelcomeScreen;