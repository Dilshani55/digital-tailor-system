import axios from 'axios';

const API = axios.create({
  baseURL: '/api',
});

export const uploadDesignImage = (formData) => API.post('/images/upload', formData);
export const saveBodyMeasurements = (data) => API.post('/measurements/', data);
export const generatePattern = (data) => API.post('/patterns/generate', data);
export const exportPDF = (data) => API.post('/export/pdf', data);

export default API;
