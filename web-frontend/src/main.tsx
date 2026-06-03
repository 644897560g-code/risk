import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { ConfigProvider, theme } from 'antd';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.defaultAlgorithm,
        token: {
          colorPrimary: '#2b5fd9',
          colorInfo: '#2b5fd9',
          colorSuccess: '#00b383',
          colorWarning: '#f5a623',
          colorError: '#e8453c',
          colorBgContainer: '#ffffff',
          colorBgElevated: '#ffffff',
          colorBorderSecondary: '#e2e6ed',
          borderRadius: 10,
          fontFamily: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`,
          fontSize: 14,
          controlHeight: 36,
          colorText: '#141b2d',
          colorTextSecondary: '#5a6070',
          colorTextTertiary: '#8c93a3',
          colorBgLayout: '#f2f4f8',
          boxShadow: '0 1px 3px rgba(0,0,0,0.04), 0 1px 2px rgba(0,0,0,0.03)',
          boxShadowSecondary: '0 4px 16px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04)',
        },
        components: {
          Layout: {
            headerBg: '#ffffff',
            siderBg: '#ffffff',
            bodyBg: '#f2f4f8',
          },
          Menu: {
            itemBg: 'transparent',
            itemSelectedBg: 'rgba(43, 95, 217, 0.08)',
            itemHoverBg: 'rgba(43, 95, 217, 0.04)',
            itemColor: '#5a6070',
            itemSelectedColor: '#2b5fd9',
          },
          Card: {
            headerBg: 'transparent',
            actionsBg: '#ffffff',
            paddingLG: 20,
          },
          Table: {
            headerBg: '#f5f6fa',
            rowHoverBg: 'rgba(43, 95, 217, 0.02)',
          },
          Tabs: {
            inkBarColor: '#2b5fd9',
            itemSelectedColor: '#2b5fd9',
            itemHoverColor: '#2b5fd9',
          },
          Button: {
            primaryShadow: '0 2px 8px rgba(43, 95, 217, 0.3)',
          },
        },
      }}
    >
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </ConfigProvider>
  </React.StrictMode>,
);
