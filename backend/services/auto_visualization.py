"""
Auto-visualization Engine - Generacion automatica de graficos INTERACTIVOS
Division Salvador, Codelco Chile

Genera visualizaciones INTERACTIVAS (Plotly) para rankings, analisis y reportes.
Soporta ordenamiento por TONELADAS o UEBD.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Colores corporativos
CODELCO_ORANGE = '#FF6B35'
CODELCO_BLUE = '#004E89'
CODELCO_GRAY = '#5A5A5A'
CODELCO_GREEN = '#06A77D'
CODELCO_RED = '#E63946'


class AutoVisualizationEngine:
    """Motor de visualizacion automatica para MineDash con Plotly."""

    def __init__(self, data_dir: Path = None, db_path: str = None):
        self.data_dir = data_dir
        self.db_path = db_path
        self.charts_dir = Path(__file__).parent.parent / "outputs" / "charts"
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        print(f"[AutoViz] Charts directory: {self.charts_dir}")

    def auto_generate_ranking_chart(
        self,
        ranking_data: List[Dict],
        year: int,
        tipo: str,
        mes: int = None,
        ordenar_por: str = "toneladas"
    ) -> Dict[str, Any]:
        """Genera grafico INTERACTIVO de barras horizontal para ranking."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            top_data = ranking_data[:10]
            if not top_data:
                raise ValueError("No hay datos para graficar")

            if ordenar_por == "uebd":
                top_data = sorted(top_data, key=lambda x: x.get("uebd", 0), reverse=True)[:10]

            operadores = [item["operador"] for item in top_data]
            toneladas = [item["toneladas_total"] for item in top_data]
            uebd = [item.get("uebd", 0) for item in top_data]
            ton_hr = [item.get("ton_por_hr_efectiva", 0) for item in top_data]
            horas = [item.get("horas_efectivas", 0) for item in top_data]
            dias = [item.get("dias_trabajados", 0) for item in top_data]
            dumps = [item.get("dumps", 0) for item in top_data]

            operadores_short = []
            for op in operadores:
                if len(op) > 25:
                    parts = op.split()
                    if len(parts) >= 2:
                        operadores_short.append(f"{parts[0]} {parts[-1][0]}.")
                    else:
                        operadores_short.append(op[:25] + "...")
                else:
                    operadores_short.append(op)

            operadores_display = operadores_short.copy()
            for i in range(min(3, len(operadores_display))):
                operadores_display[i] = f"{i+1}. " + operadores_display[i]

            operadores_display = operadores_display[::-1]
            toneladas_plot = toneladas[::-1]
            uebd_plot = uebd[::-1]
            ton_hr_plot = ton_hr[::-1]
            horas_plot = horas[::-1]
            dias_plot = dias[::-1]
            dumps_plot = dumps[::-1]

            MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            periodo = f"{MESES[mes-1]} {year}" if mes else f"Anno {year}"
            criterio_str = "UEBD" if ordenar_por == "uebd" else "Toneladas"
            titulo = f"Top 10 Operadores {tipo} - {periodo} (por {criterio_str})"

            colores = []
            for u in uebd_plot:
                if u >= 80:
                    colores.append(CODELCO_GREEN)
                elif u >= 70:
                    colores.append(CODELCO_ORANGE)
                else:
                    colores.append(CODELCO_RED)

            if ordenar_por == "uebd":
                fig = make_subplots(rows=1, cols=2, subplot_titles=["UEBD (%)", "Toneladas"],
                                   horizontal_spacing=0.15, column_widths=[0.4, 0.6])
                fig.add_trace(go.Bar(y=operadores_display, x=uebd_plot, orientation="h",
                    marker_color=colores, text=[f"{u:.1f}%" for u in uebd_plot],
                    textposition="outside", name="UEBD"), row=1, col=1)
                fig.add_trace(go.Bar(y=operadores_display, x=toneladas_plot, orientation="h",
                    marker_color=CODELCO_BLUE, text=[f"{t:,.0f}" for t in toneladas_plot],
                    textposition="outside", name="Toneladas",
                    customdata=list(zip(ton_hr_plot, horas_plot, dias_plot, dumps_plot)),
                    hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<br>Ton/Hr: %{customdata[0]:.1f}<extra></extra>"), row=1, col=2)
                fig.add_vline(x=80, line_dash="dash", line_color="green", row=1, col=1)
                fig.add_vline(x=70, line_dash="dash", line_color="orange", row=1, col=1)
            else:
                fig = go.Figure()
                fig.add_trace(go.Bar(y=operadores_display, x=toneladas_plot, orientation="h",
                    marker_color=colores, text=[f"{t:,.0f}" for t in toneladas_plot],
                    textposition="outside",
                    customdata=list(zip(uebd_plot, ton_hr_plot, horas_plot, dias_plot, dumps_plot)),
                    hovertemplate="<b>%{y}</b><br>Toneladas: %{x:,.0f}<br>UEBD: %{customdata[0]:.1f}%<br>Ton/Hr: %{customdata[1]:.1f}<extra></extra>"))
                fig.update_layout(xaxis_title="Toneladas Totales")

            fig.update_layout(title=dict(text=f"<b>{titulo}</b>", x=0.5, font=dict(size=16)),
                height=500, showlegend=False, template="plotly_white")
            fig.add_annotation(x=1.0, y=-0.12, xref="paper", yref="paper",
                text="<b>Colores UEBD:</b> Verde >=80% | Naranja 70-79% | Rojo <70%",
                showarrow=False, font=dict(size=11), align="right")

            plotly_json = fig.to_json()
            html_content = fig.to_html(full_html=False, include_plotlyjs="cdn",
                config={"displayModeBar": True, "displaylogo": False, "responsive": True})

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mes_str = f"_m{mes:02d}" if mes else ""
            chart_filename = f"ranking_{tipo}_{year}{mes_str}_{timestamp}.html"
            chart_path = self.charts_dir / chart_filename

            with open(chart_path, "w", encoding="utf-8") as f:
                f.write(f"<!DOCTYPE html><html><head><title>{titulo}</title></head><body>{html_content}</body></html>")

            print(f"    [AutoViz] Grafico interactivo guardado: {chart_path}")
            return {"plotly_json": plotly_json, "html": html_content, "type": "plotly", "chart_path": str(chart_path)}

        except ImportError:
            return self._fallback_matplotlib_ranking(ranking_data, year, tipo, mes)
        except Exception as e:
            print(f"    [AutoViz] Error: {e}")
            import traceback
            traceback.print_exc()
            raise

    def _fallback_matplotlib_ranking(self, ranking_data, year, tipo, mes=None):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import base64
        from io import BytesIO

        top_data = ranking_data[:10]
        operadores = [item["operador"][:20] for item in top_data]
        toneladas = [item["toneladas_total"] for item in top_data]

        fig, ax = plt.subplots(figsize=(14, 8))
        ax.barh(range(len(operadores)), toneladas, color=CODELCO_ORANGE)
        ax.set_yticks(range(len(operadores)))
        ax.set_yticklabels(operadores)
        ax.invert_yaxis()
        MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        titulo = f"Top 10 Operadores {tipo} - {MESES[mes-1]} {year}" if mes else f"Top 10 {tipo} - {year}"
        ax.set_title(titulo, fontweight="bold")
        plt.tight_layout()

        buffer = BytesIO()
        plt.savefig(buffer, format="png", dpi=150)
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        buffer.close()
        plt.close()
        return {"base64": f"data:image/png;base64,{img_base64}", "type": "image"}

    def generar_grafico_ranking_uebd(self, ranking_data, year, tipo, mes=None):
        return self.auto_generate_ranking_chart(ranking_data, year, tipo, mes, ordenar_por="uebd")


def generar_grafico_ranking(ranking_data, year, tipo, output_dir=None, mes=None, ordenar_por="toneladas"):
    engine = AutoVisualizationEngine()
    return engine.auto_generate_ranking_chart(ranking_data, year, tipo, mes=mes, ordenar_por=ordenar_por)

def generar_grafico_ranking_uebd(ranking_data, year, tipo, mes=None):
    engine = AutoVisualizationEngine()
    return engine.auto_generate_ranking_chart(ranking_data, year, tipo, mes, ordenar_por="uebd")
