import React from 'react';

/**
 * Panel de proceso - Muestra el estado de las herramientas ejecutadas
 * Similar a Perplexity/Claude mostrando los pasos del razonamiento
 */
const ProcessPanel = ({ steps, isProcessing }) => {
  if (!steps || steps.length === 0) return null;

  const getStepIcon = (step) => {
    if (step.status === 'running') return '⏳';
    if (step.status === 'success') return '✓';
    if (step.status === 'error') return '✗';
    return '○';
  };

  const getStepClass = (step) => {
    if (step.status === 'running') return 'step-running';
    if (step.status === 'success') return 'step-success';
    if (step.status === 'error') return 'step-error';
    return 'step-pending';
  };

  return (
    <div className={`process-panel ${isProcessing ? 'processing' : ''}`}>
      <div className="process-header">
        <span className="process-icon">
          {isProcessing ? '⚙️' : '✨'}
        </span>
        <span className="process-title">
          {isProcessing ? 'Procesando...' : 'Proceso completado'}
        </span>
      </div>

      <div className="process-steps">
        {steps.map((step, index) => (
          <div key={index} className={`process-step ${getStepClass(step)}`}>
            <span className="step-icon">{getStepIcon(step)}</span>
            <div className="step-content">
              <span className="step-description">{step.description}</span>
              {step.summary && (
                <span className="step-summary">{step.summary}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ProcessPanel;
