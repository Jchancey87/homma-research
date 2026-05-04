'use client'
import { useEffect, useState, useCallback } from 'react'
import { listJobs, retryJob, LLMJob } from '@/lib/api'
import { RefreshCw, RotateCcw, CheckCircle2, AlertCircle, Clock, Loader2 } from 'lucide-react'

const STATUS_CONFIG = {
  done:    { icon: CheckCircle2, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  error:   { icon: AlertCircle,  color: 'text-red-400',     bg: 'bg-red-500/10'     },
  pending: { icon: Clock,        color: 'text-yellow-400',  bg: 'bg-yellow-500/10'  },
  running: { icon: Loader2,      color: 'text-blue-400',    bg: 'bg-blue-500/10'    },
}

function JobRow({ job, onRetry }: { job: LLMJob; onRetry: (id: string) => void }) {
  const cfg = STATUS_CONFIG[job.status] ?? STATUS_CONFIG.pending
  const Icon = cfg.icon
  const isRetryable = job.status === 'error' || job.status === 'running'

  return (
    <div className={`flex items-center justify-between rounded-lg px-3 py-2 ${cfg.bg}`}>
      <div className="flex items-center gap-2 min-w-0">
        <Icon size={14} className={`${cfg.color} shrink-0 ${job.status === 'running' ? 'animate-spin' : ''}`} />
        <span className={`text-xs font-medium ${cfg.color} shrink-0`}>{job.status}</span>
        <span className="text-xs text-gray-300 font-mono truncate">{job.type}</span>
        {job.input_ref && (
          <span className="text-xs text-gray-500 truncate">· {job.input_ref}</span>
        )}
      </div>
      <div className="flex items-center gap-2 shrink-0 ml-2">
        <span className="text-xs text-gray-600">
          {new Date(job.updated_at).toLocaleTimeString()}
        </span>
        {isRetryable && (
          <button
            id={`retry-job-${job.id}`}
            onClick={() => onRetry(job.id)}
            title="Retry job"
            className="p-1 rounded text-gray-500 hover:text-emerald-400 hover:bg-emerald-500/10 transition-colors"
          >
            <RotateCcw size={12} />
          </button>
        )}
      </div>
    </div>
  )
}

export default function SystemStatus() {
  const [jobs, setJobs] = useState<LLMJob[]>([])
  const [loading, setLoading] = useState(true)
  const [retrying, setRetrying] = useState<string | null>(null)

  const counts = {
    done:    jobs.filter(j => j.status === 'done').length,
    error:   jobs.filter(j => j.status === 'error').length,
    pending: jobs.filter(j => j.status === 'pending').length,
    running: jobs.filter(j => j.status === 'running').length,
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setJobs(await listJobs(undefined, 20))
    } catch {
      // Backend may not be running
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleRetry = async (jobId: string) => {
    setRetrying(jobId)
    try {
      await retryJob(jobId)
      await load()
    } finally {
      setRetrying(null)
    }
  }

  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>

  return (
    <div className="space-y-4">
      {/* Summary row */}
      <div className="flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <CheckCircle2 size={13} className="text-emerald-400" />
          <span className="text-xs text-gray-400">{counts.done} done</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Loader2 size={13} className="text-blue-400" />
          <span className="text-xs text-gray-400">{counts.running} running</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Clock size={13} className="text-yellow-400" />
          <span className="text-xs text-gray-400">{counts.pending} pending</span>
        </div>
        <div className="flex items-center gap-1.5">
          <AlertCircle size={13} className="text-red-400" />
          <span className="text-xs text-gray-400">{counts.error} error{counts.error !== 1 ? 's' : ''}</span>
        </div>
        <button
          id="refresh-system-status"
          onClick={load}
          className="ml-auto p-1.5 rounded-lg text-gray-500 hover:text-white hover:bg-gray-800 transition-colors"
        >
          <RefreshCw size={13} />
        </button>
      </div>

      {/* Job list */}
      {jobs.length === 0 ? (
        <p className="text-gray-600 text-sm">No jobs yet.</p>
      ) : (
        <div className="space-y-1.5 max-h-64 overflow-y-auto pr-1">
          {jobs.map(job => (
            <JobRow
              key={job.id}
              job={retrying === job.id ? { ...job, status: 'pending' } : job}
              onRetry={handleRetry}
            />
          ))}
        </div>
      )}
    </div>
  )
}
