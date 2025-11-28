import React, { useState } from 'react';

const ChatInput = ({ onSendMessage, disabled }) => {
  const [input, setInput] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !disabled) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Enviar con Enter, nueva línea con Shift+Enter
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Escribe tu consulta..."
        className="input-textarea"
        disabled={disabled}
        rows={1}
      />
      <button 
        type="submit" 
        className="send-button"
        disabled={!input.trim() || disabled}
      >
        ➤
      </button>
    </form>
  );
};

export default ChatInput;