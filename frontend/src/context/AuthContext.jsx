import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { authApi, auth } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (auth.isAuthenticated()) {
      authApi.me()
        .then(setUser)
        .catch(() => auth.clearTokens())
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (email, password) => {
    await authApi.login(email, password);
    const me = await authApi.me();
    setUser(me);
  }, []);

  const register = useCallback(async (email, password, fullName) => {
    await authApi.register(email, password, fullName);
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    authApi.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
