import React from 'react'

interface SparklineProps {
  points?: number[]
  width?: number
  height?: number
}

export function Sparkline({ points, width = 64, height = 20 }: SparklineProps) {
  if (!points || points.length < 2) return <div style={{ width, height }} />
  
  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min
  
  const padding = 2
  
  const coords = points.map((p, idx) => {
    const x = (idx / (points.length - 1)) * (width - 2 * padding) + padding
    const y = range === 0 
      ? height / 2 
      : height - padding - ((p - min) / range) * (height - 2 * padding)
    return { x, y }
  })
  
  const pathD = coords.reduce((acc, c, idx) => {
    return acc + `${idx === 0 ? 'M' : 'L'} ${c.x.toFixed(1)} ${c.y.toFixed(1)}`
  }, '')
  
  const lastPoint = coords[coords.length - 1]
  const strokeColor = points[points.length - 1] >= points[0] ? 'var(--green)' : 'var(--red)'
  
  return (
    <svg width={width} height={height} className="overflow-visible inline-block">
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle
        cx={lastPoint.x}
        cy={lastPoint.y}
        r="2"
        fill={strokeColor}
      />
    </svg>
  )
}
