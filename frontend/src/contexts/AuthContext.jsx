import React, { createContext, useState, useContext, useEffect } from 'react';

const AuthContext = createContext();

// Usuarios hardcoded (temporalmente, luego conectar con Codelco)
const USERS = {
  'dkubota@aimine.ai': {
    password: 'MineDashAI',
    name: 'David Kubota',
    role: 'admin',
    company: 'AIMINE'
  },
  'acasa003@codelco.cl': {
    password: 'MineDashAI',
    name: 'Usuario Codelco',
    role: 'user',
    company: 'Codelco'
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Verificar si hay sesión guardada
    const savedUser = localStorage.getItem('minedash_user');
    if (savedUser) {
      setUser(JSON.parse(savedUser));
    }
    setLoading(false);
  }, []);

  const login = (email, password) => {
    const userData = USERS[email];

    if (userData && userData.password === password) {
      const userSession = {
        email,
        name: userData.name,
        role: userData.role,
        company: userData.company
      };

      setUser(userSession);
      localStorage.setItem('minedash_user', JSON.stringify(userSession));
      return { success: true };
    }

    return { success: false, error: 'Credenciales inválidas' };
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('minedash_user');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
