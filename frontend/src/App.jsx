import { useCallback, useState } from 'react'
import UploadZone from './components/UploadZone'
import SeparatorSelector from './components/SeparatorSelector'
import Dashboard from './components/Dashboard'

// Étapes du flux Phase 1 : upload -> (séparateur) -> dashboard
const STEPS = {
  UPLOAD: 'upload',
  SEPARATOR: 'separator',
  DASHBOARD: 'dashboard',
}

export default function App() {
  const [step, setStep] = useState(STEPS.UPLOAD)
  const [uploadData, setUploadData] = useState(null)
  const [parseResult, setParseResult] = useState(null)

  const handleUploaded = useCallback((data) => {
    setUploadData(data)
    if (data.already_parsed) {
      // Excel / JSON : déjà parsé côté backend, pas besoin de choisir un séparateur.
      setParseResult({
        session_id: data.session_id,
        separator: null,
        n_rows: null,
        n_columns: null,
      })
      setStep(STEPS.DASHBOARD)
    } else {
      setStep(STEPS.SEPARATOR)
    }
  }, [])

  const handleParsed = useCallback((result) => {
    setParseResult(result)
    setStep(STEPS.DASHBOARD)
  }, [])

  const handleReset = useCallback(() => {
    setUploadData(null)
    setParseResult(null)
    setStep(STEPS.UPLOAD)
  }, [])

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white px-8 py-4">
        <h1 className="text-2xl font-bold text-slate-900">DataVortex</h1>
        <p className="text-sm text-slate-500">
          Uploadez, explorez et analysez vos données
        </p>
      </header>

      <main>
        {step === STEPS.UPLOAD && <UploadZone onUploaded={handleUploaded} />}

        {step === STEPS.SEPARATOR && uploadData && (
          <SeparatorSelector
            uploadData={uploadData}
            onParsed={handleParsed}
            onCancel={handleReset}
          />
        )}

        {step === STEPS.DASHBOARD && parseResult && (
          <Dashboard
            parseResult={parseResult}
            filename={uploadData?.filename}
            onReset={handleReset}
          />
        )}
      </main>
    </div>
  )
}
