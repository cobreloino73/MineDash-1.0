import React, { useState } from 'react';
import { submitFeedback } from '../../services/api';

const FeedbackButtons = ({ interactionId, messageId }) => {
  const [feedbackGiven, setFeedbackGiven] = useState(null); // 'positive', 'negative', or null
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState('');

  const handleFeedback = async (isPositive) => {
    if (isSubmitting || feedbackGiven) return;

    setIsSubmitting(true);
    const score = isPositive ? 1.0 : 0.0;

    try {
      await submitFeedback(interactionId, score, comment || null);
      setFeedbackGiven(isPositive ? 'positive' : 'negative');
      setShowComment(false);
      setComment('');

      console.log(`✅ Feedback enviado: ${isPositive ? 'Positivo' : 'Negativo'} para interacción ${interactionId}`);
    } catch (error) {
      console.error('Error enviando feedback:', error);
      alert('Error al enviar feedback. Por favor intenta nuevamente.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleNegativeFeedback = () => {
    if (feedbackGiven) return;
    setShowComment(true);
  };

  const handleSubmitWithComment = async () => {
    await handleFeedback(false);
  };

  if (!interactionId) {
    return null; // No mostrar botones si no hay interaction_id
  }

  return (
    <div className="feedback-container" style={{
      marginTop: '12px',
      paddingTop: '12px',
      borderTop: '1px solid #e5e7eb',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }}>
      {!feedbackGiven && !showComment && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px'
        }}>
          <span style={{
            fontSize: '13px',
            color: '#6b7280',
            fontWeight: 500
          }}>
            ¿Te resultó útil?
          </span>

          <button
            onClick={() => handleFeedback(true)}
            disabled={isSubmitting}
            className="feedback-button feedback-positive"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: isSubmitting ? '#f3f4f6' : 'white',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              color: '#059669',
              transition: 'all 0.2s',
              opacity: isSubmitting ? 0.5 : 1
            }}
            onMouseEnter={(e) => {
              if (!isSubmitting) {
                e.target.style.backgroundColor = '#f0fdf4';
                e.target.style.borderColor = '#059669';
              }
            }}
            onMouseLeave={(e) => {
              if (!isSubmitting) {
                e.target.style.backgroundColor = 'white';
                e.target.style.borderColor = '#d1d5db';
              }
            }}
          >
            <span style={{ fontSize: '16px' }}>👍</span>
            Sí
          </button>

          <button
            onClick={handleNegativeFeedback}
            disabled={isSubmitting}
            className="feedback-button feedback-negative"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '6px 12px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              backgroundColor: isSubmitting ? '#f3f4f6' : 'white',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              fontSize: '13px',
              fontWeight: 500,
              color: '#dc2626',
              transition: 'all 0.2s',
              opacity: isSubmitting ? 0.5 : 1
            }}
            onMouseEnter={(e) => {
              if (!isSubmitting) {
                e.target.style.backgroundColor = '#fef2f2';
                e.target.style.borderColor = '#dc2626';
              }
            }}
            onMouseLeave={(e) => {
              if (!isSubmitting) {
                e.target.style.backgroundColor = 'white';
                e.target.style.borderColor = '#d1d5db';
              }
            }}
          >
            <span style={{ fontSize: '16px' }}>👎</span>
            No
          </button>
        </div>
      )}

      {showComment && !feedbackGiven && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '8px',
          padding: '12px',
          backgroundColor: '#fef2f2',
          borderRadius: '8px',
          border: '1px solid #fecaca'
        }}>
          <label style={{
            fontSize: '13px',
            fontWeight: 500,
            color: '#991b1b'
          }}>
            ¿Qué podríamos mejorar? (opcional)
          </label>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Cuéntanos qué salió mal o cómo podríamos mejorar..."
            rows={3}
            style={{
              width: '100%',
              padding: '8px 12px',
              border: '1px solid #fca5a5',
              borderRadius: '6px',
              fontSize: '13px',
              resize: 'vertical',
              fontFamily: 'inherit'
            }}
          />
          <div style={{
            display: 'flex',
            gap: '8px',
            justifyContent: 'flex-end'
          }}>
            <button
              onClick={() => {
                setShowComment(false);
                setComment('');
              }}
              style={{
                padding: '6px 12px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                backgroundColor: 'white',
                cursor: 'pointer',
                fontSize: '13px',
                fontWeight: 500,
                color: '#6b7280'
              }}
            >
              Cancelar
            </button>
            <button
              onClick={handleSubmitWithComment}
              disabled={isSubmitting}
              style={{
                padding: '6px 16px',
                border: 'none',
                borderRadius: '6px',
                backgroundColor: isSubmitting ? '#9ca3af' : '#dc2626',
                color: 'white',
                cursor: isSubmitting ? 'not-allowed' : 'pointer',
                fontSize: '13px',
                fontWeight: 500,
                opacity: isSubmitting ? 0.6 : 1
              }}
            >
              {isSubmitting ? 'Enviando...' : 'Enviar feedback'}
            </button>
          </div>
        </div>
      )}

      {feedbackGiven && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          padding: '8px 12px',
          backgroundColor: feedbackGiven === 'positive' ? '#f0fdf4' : '#fef2f2',
          borderRadius: '6px',
          border: `1px solid ${feedbackGiven === 'positive' ? '#bbf7d0' : '#fecaca'}`,
          fontSize: '13px',
          color: feedbackGiven === 'positive' ? '#059669' : '#dc2626',
          fontWeight: 500
        }}>
          <span style={{ fontSize: '16px' }}>
            {feedbackGiven === 'positive' ? '✓' : '✓'}
          </span>
          Gracias por tu feedback
        </div>
      )}
    </div>
  );
};

export default FeedbackButtons;
