# CODIGOS ASARCO - DOCUMENTACION EXTRAIDA DE BD REAL
**Fecha extraccion:** 2025-11-20 15:48:21
**Fuente:** hexagon_estados (minedash.db)

---

## RESUMEN EJECUTIVO

- **Total codigos unicos:** 65
- **Total eventos registrados:** 494,587
- **Total horas de delays:** 2,018,188

## DISTRIBUCION POR CATEGORIA

| Categoria | Codigos | Eventos | Horas | % Total |
|-----------|---------|---------|-------|---------|
| EFECTIVO | 5 | 133,721 | 679,532 | 33.67% |
| DET.NOPRG. | 33 | 109,588 | 496,143 | 24.58% |
| DET.PROG. | 14 | 197,681 | 394,668 | 19.56% |
| M. CORRECTIVA | 4 | 45,743 | 383,742 | 19.01% |
| M. PROGRAMADA | 7 | 7,792 | 63,543 | 3.15% |
| RESERVA | 0 | 62 | 560 | 0.03% |

## TOP 20 CODIGOS POR IMPACTO

| Codigo | Categoria | Razon | Eventos | Horas | % | Equipos |
|--------|-----------|-------|---------|-------|---|---------|
| 1.0 | EFECTIVO | PRODUCCION | 132,335 | 676,538 | 33.52% | 154 |
| 225.0 | DET.NOPRG. | SIN OPERADOR | 61,635 | 437,886 | 21.7% | 154 |
| 400.0 | M. CORRECTIVA | IMPREVISTO MECANICO | 44,515 | 380,993 | 18.88% | 151 |
| 243.0 | DET.PROG. | CAMBIO TURNO | 137,710 | 337,374 | 16.72% | 154 |
| 402.0 | M. PROGRAMADA | MANTENIMIENTO PROGRAMADO | 7,224 | 62,169 | 3.08% | 141 |
| 242.0 | DET.PROG. | COLACION | 34,606 | 49,587 | 2.46% | 153 |
| 220.0 | DET.NOPRG. | FUERZA MAYOR | 2,104 | 15,793 | 0.78% | 135 |
| 213.0 | DET.NOPRG. | OTRAS DEMORAS | 8,172 | 15,568 | 0.77% | 146 |
| 212.0 | DET.NOPRG. | ESPERA MARCACION | 1,076 | 6,912 | 0.34% | 35 |
| 219.0 | DET.NOPRG. | FALTA EQUIPO CARGUIO | 20,874 | 6,126 | 0.3% | 62 |
| 236.0 | DET.PROG. | ABASTECIMIENTO COMBUSTIBLE | 14,312 | 3,616 | 0.18% | 136 |
| 247.0 | DET.NOPRG. | CONDICIONES CLIMATICAS | 643 | 3,172 | 0.16% | 129 |
| 210.0 | DET.NOPRG. | ESPERA TRASLADO | 3,258 | 2,823 | 0.14% | 57 |
| 211.0 | M. CORRECTIVA | EVENTO NEUMATICOS | 1,179 | 2,689 | 0.13% | 70 |
| 209.0 | DET.NOPRG. | ESPERA SITIO PARA PERFORAR | 360 | 2,392 | 0.12% | 22 |
| 3.0 | EFECTIVO | NO PRODUCTIVO | 553 | 1,472 | 0.07% | 95 |
| 229.0 | DET.NOPRG. | ESPERA POR TRONADURA | 1,401 | 1,211 | 0.06% | 131 |
| 244.0 | DET.PROG. | TRASLADO DE EQUIPO A MANTENIMIENTO | 1,045 | 1,183 | 0.06% | 128 |
| 202.0 | DET.NOPRG. | ESPERA COMBUSTIBLE | 1,903 | 1,024 | 0.05% | 103 |
| 228.0 | DET.NOPRG. | REUNION | 1,108 | 927 | 0.05% | 132 |

## CODIGOS DETALLADOS POR CATEGORIA

### DET.NOPRG.

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| 225.0 | SIN OPERADOR | 61,635 | 437,886 | 7.1 | 154 | 2024-01-01 | 2025-09-10 |
| 220.0 | FUERZA MAYOR | 2,104 | 15,793 | 7.51 | 135 | 2024-02-01 | 2025-09-08 |
| 213.0 | OTRAS DEMORAS | 8,172 | 15,568 | 1.91 | 146 | 2024-01-01 | 2025-09-10 |
| 212.0 | ESPERA MARCACION | 1,076 | 6,912 | 6.42 | 35 | 2024-01-02 | 2025-08-18 |
| 219.0 | FALTA EQUIPO CARGUIO | 20,874 | 6,126 | 0.29 | 62 | 2024-01-01 | 2025-09-10 |
| 247.0 | CONDICIONES CLIMATICAS | 643 | 3,172 | 4.93 | 129 | 2024-01-25 | 2025-09-07 |
| 210.0 | ESPERA TRASLADO | 3,258 | 2,823 | 0.87 | 57 | 2024-01-01 | 2025-09-10 |
| 209.0 | ESPERA SITIO PARA PERFORAR | 360 | 2,392 | 6.64 | 22 | 2024-01-01 | 2025-09-02 |
| 229.0 | ESPERA POR TRONADURA | 1,401 | 1,211 | 0.86 | 131 | 2024-01-05 | 2025-09-10 |
| 202.0 | ESPERA COMBUSTIBLE | 1,903 | 1,024 | 0.54 | 103 | 2024-01-01 | 2025-09-09 |
| 228.0 | REUNION | 1,108 | 927 | 0.84 | 132 | 2024-01-02 | 2025-09-09 |
| 204.0 | ESPERA POR COLACION | 1,851 | 909 | 0.49 | 74 | 2024-01-10 | 2025-09-10 |
| 223.0 | CHANCADOR NO DISPONIBLE | 1,851 | 464 | 0.25 | 46 | 2024-05-02 | 2025-09-10 |
| 221.0 | STOCK LLENO | 236 | 203 | 0.86 | 38 | 2024-01-05 | 2025-09-09 |
| 205.0 | BAÑO | 734 | 129 | 0.18 | 47 | 2024-01-02 | 2025-09-10 |
| 203.0 | ESPERA DE AGUA | 72 | 107 | 1.49 | 29 | 2024-01-11 | 2025-09-04 |
| 215.0 | OBSTRUCCION VIAS | 886 | 97 | 0.11 | 40 | 2024-01-01 | 2025-09-10 |
| 208.0 | SIN MALLA EN SISTEMA | 36 | 83 | 2.31 | 22 | 2024-01-14 | 2024-12-08 |
| 227.0 | FALTA DE MATERIAL | 174 | 61 | 0.35 | 83 | 2024-01-02 | 2025-09-10 |
| 248.0 | TOPOGRAFIA | 344 | 47 | 0.14 | 43 | 2024-01-01 | 2025-09-10 |
| 224.0 | EVENTO GEOTECNICO | 319 | 44 | 0.14 | 130 | 2024-01-05 | 2025-09-07 |
| 250.0 | ATOLLO EN CHANCADO | 72 | 44 | 0.61 | 24 | 2024-03-07 | 2025-08-07 |
| 230.0 | INTERFERENCIA POR SISTEMA DE DESPACHO | 66 | 39 | 0.6 | 30 | 2024-01-10 | 2025-08-10 |
| 218.0 | FATIGA | 44 | 24 | 0.54 | 29 | 2024-01-09 | 2025-08-15 |
| 216.0 | SOBRECARGA O MAL ESTIBADO | 23 | 12 | 0.54 | 17 | 2024-02-19 | 2025-06-24 |
| 217.0 | ACERO PEGADO | 6 | 10 | 1.73 | 6 | 2024-07-26 | 2025-03-20 |
| 222.0 | BOTADERO NO DISPONIBLE | 105 | 10 | 0.1 | 36 | 2024-01-14 | 2025-09-07 |
| 248.0 | POLUCION | 84 | 6 | 0.07 | 26 | 2024-01-05 | 2024-12-02 |
| 251.0 | DNP - REPARACION TECNOLOGIAS/SISTEMAS (NO JIGSAW) | 24 | 6 | 0.24 | 21 | 2024-11-23 | 2025-08-08 |
| 201.0 | CAFE, BEBESTIBLE, TERMO | 41 | 5 | 0.13 | 30 | 2024-03-19 | 2025-08-18 |

### DET.PROG.

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| 243.0 | CAMBIO TURNO | 137,710 | 337,374 | 2.45 | 154 | 2024-01-01 | 2025-09-10 |
| 242.0 | COLACION | 34,606 | 49,587 | 1.43 | 153 | 2024-01-01 | 2025-09-10 |
| 236.0 | ABASTECIMIENTO COMBUSTIBLE | 14,312 | 3,616 | 0.25 | 136 | 2024-01-01 | 2025-09-10 |
| 244.0 | TRASLADO DE EQUIPO A MANTENIMIENTO | 1,045 | 1,183 | 1.13 | 128 | 2024-01-04 | 2025-09-10 |
| 214.0 | LIMPIEZA DE CANCHA | 4,267 | 913 | 0.21 | 42 | 2024-01-02 | 2025-09-10 |
| 238.0 | TRONADURA | 1,316 | 795 | 0.6 | 99 | 2024-01-03 | 2025-09-10 |
| 239.0 | RELEVO | 2,973 | 582 | 0.2 | 100 | 2024-01-01 | 2025-09-09 |
| 233.0 | CAMBIO MODULO | 270 | 208 | 0.77 | 71 | 2024-03-03 | 2025-09-08 |
| 241.0 | ABASTECIMIENTO DE AGUA | 280 | 187 | 0.67 | 57 | 2024-01-05 | 2025-07-22 |
| 234.0 | CHEQUEO PRE-OPERACIONAL | 786 | 163 | 0.21 | 46 | 2024-01-04 | 2025-09-10 |
| 237.0 | CAMBIO DE ACEROS | 53 | 59 | 1.12 | 33 | 2024-01-03 | 2025-09-09 |
| 240.0 | ROTACION DE BARRAS | 40 | 0 | 0.01 | 24 | 2024-01-29 | 2025-06-26 |
| 246.0 | CORTE ENERGIA OPERACIONAL | 18 | 0 | 0.01 | 16 | 2024-02-25 | 2025-07-15 |
| 235.0 | CORTE ENERGIA OPERACIONAL | 5 | 0 | 0.0 | 5 | 2024-01-03 | 2025-01-09 |

### EFECTIVO

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| 1.0 | PRODUCCION | 132,335 | 676,538 | 5.11 | 154 | 2024-01-01 | 2025-09-10 |
| 3.0 | NO PRODUCTIVO | 553 | 1,472 | 2.66 | 95 | 2024-01-01 | 2025-09-09 |
| 245.0 | ENTRENAMIENTO SIN PRODUCCION | 184 | 906 | 4.92 | 33 | 2024-01-20 | 2025-09-02 |
| 2.0 | ENTRENAMIENTO | 629 | 590 | 0.94 | 134 | 2024-01-03 | 2025-09-10 |
| 232.0 | CAMBIO DE POZO | 20 | 26 | 1.29 | 10 | 2024-02-10 | 2025-09-06 |

### M. CORRECTIVA

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| 400.0 | IMPREVISTO MECANICO | 44,515 | 380,993 | 8.56 | 151 | 2024-01-01 | 2025-09-10 |
| 211.0 | EVENTO NEUMATICOS | 1,179 | 2,689 | 2.28 | 70 | 2024-01-01 | 2025-09-10 |
| 253.0 | MNP - REPARACION SISTEMA CAS (JIGSAW) | 20 | 35 | 1.73 | 14 | 2024-11-19 | 2025-08-11 |
| 254.0 | MNP - REPARACION SISTEMA OAS (JIGSAW) | 29 | 26 | 0.88 | 20 | 2024-11-20 | 2025-08-14 |

### M. PROGRAMADA

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| 402.0 | MANTENIMIENTO PROGRAMADO | 7,224 | 62,169 | 8.61 | 141 | 2024-01-01 | 2025-09-10 |
| 403.0 | INSTALACION JIGSAW | 215 | 468 | 2.18 | 49 | 2024-03-19 | 2025-07-24 |
| 407.0 | MP - SISTEMA CAS (JIGSAW) | 124 | 290 | 2.34 | 35 | 2024-10-08 | 2025-09-07 |
| 406.0 | MP - SISTEMA FMS (JIGSAW) | 90 | 224 | 2.49 | 32 | 2024-10-02 | 2025-09-03 |
| 401.0 | PARQUE DE REPARACION INVERSIONAL | 31 | 223 | 7.18 | 13 | 2024-01-09 | 2024-10-09 |
| 408.0 | MP - SISTEMA OAS (JIGSAW) | 51 | 92 | 1.79 | 29 | 2024-10-19 | 2025-09-09 |
| 404.0 | MP - INSTALACION TECNOLOGIAS/SISTEMAS (NO JIGSAW) | 57 | 76 | 1.34 | 26 | 2024-11-27 | 2025-09-05 |

### RESERVA

| Codigo | Razon | Eventos | Horas | Duracion Prom | Equipos | Primera | Ultima |
|--------|-------|---------|-------|---------------|---------|---------|--------|
| nan | N/A | 62 | 560 | 9.04 | 4 | 2024-07-12 | 2025-09-10 |
