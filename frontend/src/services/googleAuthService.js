import axios from 'axios';

const BASE_URL = 'http://127.0.0.1:5000/api';

export const googleAuthService = {
  /**
   * Triggers the Google OAuth flow and posts the token to backend /auth/google endpoint.
   * @param {string} authCode - OAuth code or credential token from Google Identity Services
   */
  authenticateWithGoogle: async (authCode) => {
    const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
    
    if (!clientId) {
      console.warn("VITE_GOOGLE_CLIENT_ID is not configured in your .env file.");
      throw new Error("Google Sign-In is not configured yet. Please define VITE_GOOGLE_CLIENT_ID in your environment variables.");
    }

    try {
      const response = await axios.post(`${BASE_URL}/auth/google`, {
        code: authCode,
        client_id: clientId
      }, {
        headers: { 'Content-Type': 'application/json' }
      });

      return response.data; // Expected response: { token, user }
    } catch (error) {
      if (error.response?.status === 400) {
        throw new Error("Your Google account could not be authenticated.");
      }
      throw new Error(error.response?.data?.error || "Unable to sign in with Google. Please try again.");
    }
  }
};
