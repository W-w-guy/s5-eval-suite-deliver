import React, { useState } from 'react'
import QualityBoard from './pages/QualityBoard'
import RejectedList from './pages/RejectedList'

export default function App() {
  const [drill, setDrill] = useState<string | null>(null)
  return drill ? (
    <RejectedList
      toolKey={drill}
      onBack={() => setDrill(null)}
      onOpenInQueue={() => {
        /* 真实实现会跳 /eval/review?draft=... 并由后端做权限校验 */
      }}
    />
  ) : (
    <QualityBoard onDrilldown={(k) => setDrill(k)} />
  )
}
