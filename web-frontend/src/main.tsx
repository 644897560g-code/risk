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
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: '#37e7ff',
          colorInfo: '#37e7ff',
          colorSuccess: '#34d399',
          colorWarning: '#fbbf24',
          colorError: '#fb7185',
          colorBgContainer: '#0c121c',
          colorBgElevated: '#0f172a',
          colorBorder: 'rgba(55, 231, 255, 0.18)',
          colorBorderSecondary: 'rgba(148, 163, 184, 0.16)',
          borderRadius: 10,
          fontFamily: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`,
          fontSize: 14,
          controlHeight: 36,
          colorText: '#dbeafe',
          colorTextSecondary: 'rgba(226, 232, 240, 0.68)',
          colorTextTertiary: 'rgba(226, 232, 240, 0.5)',
          colorBgLayout: '#080d15',
          boxShadow: '0 12px 30px rgba(0,0,0,0.22)',
          boxShadowSecondary: '0 24px 70px rgba(0,0,0,0.38)',
        },
        components: {
          Layout: {
            headerBg: '#090d13',
            siderBg: '#0a0f18',
            bodyBg: '#080d15',
          },
          Menu: {
            itemBg: 'transparent',
            itemSelectedBg: 'rgba(55, 231, 255, 0.14)',
            itemHoverBg: 'rgba(55, 231, 255, 0.08)',
            itemColor: 'rgba(226, 232, 240, 0.68)',
            itemSelectedColor: '#37e7ff',
            groupTitleColor: 'rgba(226, 232, 240, 0.38)',
          },
          Card: {
            headerBg: 'transparent',
            actionsBg: '#0c121c',
            paddingLG: 20,
          },
          Table: {
            headerBg: 'rgba(15, 23, 42, 0.92)',
            rowHoverBg: 'rgba(55, 231, 255, 0.06)',
            borderColor: 'rgba(148, 163, 184, 0.14)',
          },
          Tabs: {
            inkBarColor: '#37e7ff',
            itemSelectedColor: '#37e7ff',
            itemHoverColor: '#67e8f9',
          },
          Button: {
            primaryShadow: '0 0 18px rgba(55, 231, 255, 0.24)',
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
