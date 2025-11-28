"""
WATERFALL CORRECTO USANDO PLOTLY
Reemplazo para el método _generate_waterfall de chart_tool.py

Este código genera waterfalls CORRECTOS como la imagen de ejemplo del usuario.
"""
from pathlib import Path
from typing import Dict, Any
from datetime import datetime


def generate_waterfall_plotly(
    data: Dict[str, Any],
    title: str,
    ylabel: str = '',
    charts_dir: Path = None
) -> Path:
    """
    Generar gráfico waterfall usando Plotly (CORRECTO como imagen de ejemplo)

    Formato esperado:
    {
        "x": ["Plan", "Factor1", "Factor2", ..., "Real"],
        "y": [9430808, -774250, -554000, ..., 0],
        "measures": ["absolute", "relative", "relative", ..., "total"]
    }

    CRÍTICO: El último valor DEBE ser 0, Plotly calcula automáticamente el total
    """
    try:
        import plotly.graph_objects as go

        x_labels = data.get('x', [])
        values = data.get('y', [])
        measures = data.get('measures', ['relative'] * len(values))

        if not x_labels or not values:
            raise ValueError("Se requieren 'x' e 'y' para waterfall chart")

        # Formatear valores para texto (M = millones, K = miles)
        text_values = []
        for v in values:
            if v == 0:
                text_values.append("")  # No mostrar texto para el total (Plotly lo calcula)
            elif abs(v) >= 1_000_000:
                text_values.append(f"{v/1e6:.2f}M")
            elif abs(v) >= 1_000:
                text_values.append(f"{v/1e3:.0f}K")
            else:
                text_values.append(f"{v:.0f}")

        # Crear waterfall con Plotly
        fig = go.Figure(go.Waterfall(
            name="Cumplimiento",
            orientation="v",
            x=x_labels,
            y=values,
            measure=measures,
            text=text_values,
            textposition="outside",
            connector={"line": {"color": "gray", "width": 1, "dash": "dot"}},
            increasing={"marker": {"color": "#2E7D32"}},  # Verde para positivos
            decreasing={"marker": {"color": "#C62828"}},  # Rojo para pérdidas
            totals={"marker": {"color": "#1565C0"}}       # Azul para total
        ))

        # Layout
        fig.update_layout(
            title=title,
            showlegend=False,
            yaxis_title=ylabel if ylabel else "Toneladas",
            yaxis_tickformat=".2s",
            xaxis=dict(tickangle=-45),
            height=600,
            width=1200,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(size=12)
        )

        # Guardar como HTML (interactivo - no requiere kaleido)
        if charts_dir is None:
            charts_dir = Path(__file__).parent.parent / "outputs" / "charts"

        charts_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"chart_waterfall_{timestamp}.html"
        filepath = charts_dir / filename

        # HTML interactivo - hover, zoom, pan, etc.
        fig.write_html(str(filepath), include_plotlyjs=True, full_html=True)

        return filepath

    except Exception as e:
        raise Exception(f"Error generando waterfall Plotly: {str(e)}")


# Test si se ejecuta directamente
if __name__ == "__main__":
    # Datos de ejemplo
    test_data = {
        'x': ['Plan', 'SIN OPERADOR', 'IMPREVISTO', 'CAMBIO TURNO', 'COLACIÓN', 'Real'],
        'y': [9430808, -774250, -554000, -335750, -83325, 0],
        'measures': ['absolute', 'relative', 'relative', 'relative', 'relative', 'total']
    }

    path = generate_waterfall_plotly(
        data=test_data,
        title="Cascada de Cumplimiento - Enero 2025",
        ylabel="Toneladas"
    )

    print(f"[OK] Waterfall generado: {path}")
