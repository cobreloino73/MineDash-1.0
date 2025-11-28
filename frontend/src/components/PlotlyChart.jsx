import React, { useMemo } from 'react';
import Plot from 'react-plotly.js';

/**
 * Componente para renderizar gráficos Plotly interactivos
 *
 * Props:
 * - chart: objeto con { plotly_json, html, type } o { base64, type }
 * - height: altura del gráfico (default: 500)
 */
const PlotlyChart = ({ chart, height = 500 }) => {
  // Parse plotly_json si es string
  const plotData = useMemo(() => {
    if (!chart) return null;

    if (chart.type === 'plotly' && chart.plotly_json) {
      try {
        const parsed = typeof chart.plotly_json === 'string'
          ? JSON.parse(chart.plotly_json)
          : chart.plotly_json;
        return parsed;
      } catch (e) {
        console.error('Error parsing plotly_json:', e);
        return null;
      }
    }
    return null;
  }, [chart]);

  if (!chart) {
    return null;
  }

  // Renderizar gráfico Plotly interactivo
  if (chart.type === 'plotly' && plotData) {
    return (
      <div className="plotly-chart-container" style={{
        width: '100%',
        marginTop: '16px',
        marginBottom: '16px',
        borderRadius: '8px',
        overflow: 'hidden',
        boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
      }}>
        <Plot
          data={plotData.data || []}
          layout={{
            ...plotData.layout,
            height: height,
            autosize: true,
            margin: { t: 60, r: 30, b: 60, l: 60 }
          }}
          config={{
            responsive: true,
            displaylogo: false,
            displayModeBar: true,
            modeBarButtonsToRemove: ['lasso2d', 'select2d', 'autoScale2d'],
            toImageButtonOptions: {
              format: 'png',
              filename: 'minedash_chart',
              height: 600,
              width: 1200,
              scale: 2
            }
          }}
          style={{ width: '100%', height: `${height}px` }}
          useResizeHandler={true}
        />
      </div>
    );
  }

  // Fallback: imagen estática (base64)
  if (chart.type === 'image' && chart.base64) {
    return (
      <div className="static-chart-container" style={{
        width: '100%',
        marginTop: '16px',
        marginBottom: '16px'
      }}>
        <img
          src={chart.base64}
          alt="Gráfico generado"
          style={{
            maxWidth: '100%',
            height: 'auto',
            borderRadius: '8px',
            boxShadow: '0 4px 6px rgba(0,0,0,0.1)'
          }}
        />
      </div>
    );
  }

  // Fallback: HTML embebido
  if (chart.html) {
    return (
      <div
        className="embedded-chart-container"
        style={{
          width: '100%',
          marginTop: '16px',
          marginBottom: '16px'
        }}
        dangerouslySetInnerHTML={{ __html: chart.html }}
      />
    );
  }

  return null;
};

export default PlotlyChart;
