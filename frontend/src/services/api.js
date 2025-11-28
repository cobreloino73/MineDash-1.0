import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const getRankingProduccion = (year = 2024, topN = 10, tipo = '') => {
  return api.get('/api/ranking/operadores-produccion', {
    params: { year, top_n: topN, tipo }
  });
};

export const getAnalisisCausal = (apellido, year = 2024, mesInicio = 1, mesFin = 12) => {
  return api.get('/api/analytics/operador-causal', {
    params: { apellido, year, mes_inicio: mesInicio, mes_fin: mesFin }
  });
};

export const sendRAGQuery = (query, mode = 'hybrid') => {
  return api.post('/api/query', { query, mode });
};

export default api;