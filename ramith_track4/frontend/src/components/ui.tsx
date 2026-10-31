import type { ComponentProps, ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const inputCls =
  'w-full rounded-md border border-line2 bg-bg px-2.5 py-1.5 text-ink placeholder:text-dim transition-colors hover:border-[#46617d] focus:border-cyan focus:outline-none focus:ring-2 focus:ring-cyan/20'

export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return <span className={cn('inline-flex items-center gap-1.5 whitespace-nowrap rounded border px-2 py-px text-[10.5px] font-bold tracking-wider', className)}>{children}</span>
}

type BtnProps = ComponentProps<'button'> & { variant?: 'default' | 'primary' | 'ghost'; size?: 'sm' | 'md' }
export function Btn({ variant = 'default', size = 'md', className, ...p }: BtnProps) {
  return (
    <button
      {...p}
      className={cn(
        'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-md border font-semibold transition-all active:translate-y-px disabled:cursor-not-allowed disabled:opacity-45',
        size === 'sm' ? 'h-8 px-3 text-xs' : 'h-9 px-3.5 text-[13px]',
        variant === 'primary' && 'border-[#3b6db3] bg-[#2a5a9e] text-white hover:bg-[#3369b3]',
        variant === 'default' && 'border-line2 bg-panel3 text-ink hover:border-[#46617d] hover:bg-[#223648]',
        variant === 'ghost' && 'border-transparent bg-transparent text-mute hover:bg-panel2 hover:text-ink',
        className,
      )}
    />
  )
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('text-[10.5px] font-bold uppercase tracking-[0.14em] text-dim', className)}>{children}</div>
}

export function Pane({ title, icon, actions, children, className, bodyClass }: { title: string; icon?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string }) {
  return (
    <section aria-label={title} className={cn('flex min-h-0 flex-col overflow-hidden rounded-lg border border-line bg-panel', className)}>
      <header className="flex min-h-11 items-center justify-between gap-2 border-b border-line px-3.5 py-2">
        <h2 className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.13em] text-mute">{icon}{title}</h2>
        {actions}
      </header>
      <div className={cn('flex min-h-0 flex-1 flex-col gap-3 overflow-auto p-3.5', bodyClass)}>{children}</div>
    </section>
  )
}

export function EmptyState({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="flex flex-col items-center gap-2 px-4 py-8 text-center text-mute">
      <div className="grid size-10 place-items-center rounded-full bg-panel3 text-cyan">{icon}</div>
      <h3 className="text-sm font-semibold text-ink">{title}</h3>
      <p className="max-w-[36ch] text-[12.5px]">{text}</p>
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('h-3 animate-pulse rounded bg-panel3', className)} />
}
