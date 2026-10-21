import ReplikersWorldPortal from "./components/ReplikersWorldPortal";
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from "./WorldApp.tsx"

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ReplikersWorldPortal><App /></ReplikersWorldPortal>
  </StrictMode>,
)
