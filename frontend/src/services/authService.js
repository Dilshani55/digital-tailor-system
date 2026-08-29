import { authAPI } from './api';

export const authService = {
  login: async (email, password) => {
    try {
      const response = await authAPI.login({ email, password });
      return response.data; // returns { token, user }
    } catch (error) {
      throw error.response?.data?.error || 'Login failed. Please check your credentials.';
    }
  },

  register: async (fullName, email, password) => {
    try {
      const response = await authAPI.register({
        full_name: fullName,
        email,
        password
      });
      return response.data;
    } catch (error) {
      throw error.response?.data?.error || 'Registration failed. Please try again.';
    }
  }
};
