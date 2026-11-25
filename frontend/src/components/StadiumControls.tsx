import React, { forwardRef, useEffect, useId, useMemo, useRef, useState } from 'react'
import { StadiumIcon, type StadiumIconName } from './StadiumIcons'

/* ==========================================================================
   1. STADIUM FIELD
   ========================================================================== */
export interface StadiumFieldProps {
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  htmlFor?: string
  className?: string
  children: React.ReactNode
}

export function StadiumField({
  label,
  hint,
  error,
  required,
  htmlFor,
  className = '',
  children,
}: StadiumFieldProps) {
  return (
    <div className={`stadium-field ${className}`}>
      {label && (
        <label className="stadium-field-label" htmlFor={htmlFor}>
          <span>
            {label}
            {required && <span style={{ color: 'var(--accent-lime)', marginLeft: '3px' }}>*</span>}
          </span>
        </label>
      )}
      {children}
      {hint && <span className="stadium-field-hint">{hint}</span>}
      {error && (
        <span className="stadium-field-error" role="alert">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </span>
      )}
    </div>
  )
}

/* ==========================================================================
   2. STADIUM INPUT
   ========================================================================== */
export interface StadiumInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode
  clearable?: boolean
  onClear?: () => void
}

export const StadiumInput = forwardRef<HTMLInputElement, StadiumInputProps>(function StadiumInput(
  { icon, clearable, onClear, className = '', value, ...props },
  ref
) {
  const hasValue = value != null && value !== ''

  return (
    <div className="stadium-input-wrapper">
      {icon && <span className="stadium-input-icon">{icon}</span>}
      <input
        ref={ref}
        value={value}
        className={`stadium-input ${icon ? 'stadium-input-with-icon' : ''} ${className}`}
        {...props}
      />
      {clearable && hasValue && onClear && (
        <button
          type="button"
          className="stadium-input-clear-btn"
          onClick={onClear}
          aria-label="Clear input"
        >
          ✕
        </button>
      )}
    </div>
  )
})

/* ==========================================================================
   3. STADIUM SELECT (Custom Trigger + Accessible Option Popup)
   ========================================================================== */
export interface StadiumSelectOption {
  value: string
  label: string
  icon?: string
  badge?: string
}

export interface StadiumSelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'onChange' | 'value'> {
  value?: string
  onChange?: (val: string, e?: React.ChangeEvent<HTMLSelectElement>) => void
  options?: StadiumSelectOption[]
  placeholder?: string
  searchable?: boolean
  children?: React.ReactNode
  className?: string
  'aria-label'?: string
}

export const StadiumSelect = forwardRef<HTMLSelectElement, StadiumSelectProps>(function StadiumSelect(
  {
    value = '',
    onChange,
    options: directOptions,
    placeholder = 'Select an option…',
    disabled,
    id,
    children,
    className = '',
    'aria-label': ariaLabel,
    ...props
  },
  ref
) {
  const [isOpen, setIsOpen] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(-1)
  const containerRef = useRef<HTMLDivElement>(null)
  const nativeSelectRef = useRef<HTMLSelectElement | null>(null)
  const popupRef = useRef<HTMLDivElement>(null)

  // Parse options from either `options` prop or `<option>` children
  const parsedOptions = useMemo<StadiumSelectOption[]>(() => {
    if (directOptions && directOptions.length > 0) return directOptions
    const list: StadiumSelectOption[] = []
    React.Children.forEach(children, child => {
      if (React.isValidElement(child) && child.type === 'option') {
        const val = child.props.value !== undefined ? String(child.props.value) : String(child.props.children ?? '')
        const lbl = String(child.props.children ?? val)
        list.push({ value: val, label: lbl })
      }
    })
    return list
  }, [directOptions, children])

  const selectedOption = parsedOptions.find(o => String(o.value) === String(value))
  const displayLabel = selectedOption?.label ?? (value ? String(value) : placeholder)

  // Connect forwarded ref
  const setNativeRef = (el: HTMLSelectElement | null) => {
    nativeSelectRef.current = el
    if (typeof ref === 'function') ref(el)
    else if (ref) ref.current = el
  }

  // Close on outside click
  useEffect(() => {
    if (!isOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  // Scroll highlighted item into view
  useEffect(() => {
    if (!isOpen || highlightedIndex < 0 || !popupRef.current) return
    const items = popupRef.current.querySelectorAll('.stadium-dropdown-option')
    if (items[highlightedIndex]) {
      (items[highlightedIndex] as HTMLElement).scrollIntoView({ block: 'nearest' })
    }
  }, [isOpen, highlightedIndex])

  function selectValue(val: string) {
    if (nativeSelectRef.current) {
      nativeSelectRef.current.value = val
      // Dispatch synthetic event for listeners
      const event = new Event('change', { bubbles: true })
      nativeSelectRef.current.dispatchEvent(event)
    }
    if (onChange) {
      onChange(val)
    }
    setIsOpen(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (disabled) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!isOpen) {
        setIsOpen(true)
        setHighlightedIndex(0)
      } else {
        setHighlightedIndex(i => (i + 1 < parsedOptions.length ? i + 1 : 0))
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (!isOpen) {
        setIsOpen(true)
        setHighlightedIndex(parsedOptions.length - 1)
      } else {
        setHighlightedIndex(i => (i - 1 >= 0 ? i - 1 : parsedOptions.length - 1))
      }
    } else if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      if (isOpen && highlightedIndex >= 0 && parsedOptions[highlightedIndex]) {
        selectValue(parsedOptions[highlightedIndex].value)
      } else {
        setIsOpen(!isOpen)
      }
    } else if (e.key === 'Escape' && isOpen) {
      e.preventDefault()
      setIsOpen(false)
    }
  }

  return (
    <div className={`stadium-select-wrapper ${className}`} ref={containerRef}>
      {/* Hidden native select for 100% test & screen-reader compatibility */}
      <select
        ref={setNativeRef}
        id={id}
        value={value}
        disabled={disabled}
        aria-label={ariaLabel}
        onChange={e => {
          if (onChange) onChange(e.target.value, e)
        }}
        onKeyDown={e => {
          if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setIsOpen(true)
            setHighlightedIndex(0)
          }
        }}
        className="stadium-native-select-proxy"
        {...props}
      >
        {children ? children : (
          parsedOptions.map(o => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))
        )}
      </select>

      {/* Premium Visual Trigger (Decorated for sighted users) */}
      <button
        type="button"
        id={id ? `${id}-trigger` : undefined}
        tabIndex={-1}
        aria-hidden="true"
        disabled={disabled}
        className={`stadium-select-trigger ${isOpen ? 'is-open' : ''}`}
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
      >
        <span className="stadium-select-value">
          {selectedOption?.icon && <span>{selectedOption.icon}</span>}
          <span>{displayLabel}</span>
          {selectedOption?.badge && <span className="badge lime sm">{selectedOption.badge}</span>}
        </span>
        <span className="stadium-select-chevron" aria-hidden="true">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </span>
      </button>

      {/* Accessible Dropdown Popup */}
      {isOpen && (
        <div
          ref={popupRef}
          role="listbox"
          aria-label={ariaLabel}
          className="stadium-dropdown-popup"
        >
          {parsedOptions.map((opt, idx) => {
            const isSelected = String(opt.value) === String(value)
            const isHighlighted = idx === highlightedIndex
            return (
              <button
                type="button"
                role="option"
                key={opt.value}
                aria-selected={isSelected}
                className={`stadium-dropdown-option ${isSelected ? 'is-selected' : ''} ${isHighlighted ? 'is-highlighted' : ''}`}
                onClick={() => selectValue(opt.value)}
                onMouseEnter={() => setHighlightedIndex(idx)}
              >
                <span className="row gap05 align-center">
                  {opt.icon && <span>{opt.icon}</span>}
                  <span>{opt.label}</span>
                </span>
                {isSelected && <span className="stadium-dropdown-option-check">✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
})

/* ==========================================================================
   4. STADIUM COMBOBOX (Searchable PlayStyle & Attribute Selector)
   ========================================================================== */
export const DEFAULT_PLAYSTYLES_PLUS = [
  'Finesse Shot+',
  'Power Shot+',
  'Chip Shot+',
  'Power Header+',
  'Dead Ball+',
  'Incisive Pass+',
  'Pinged Pass+',
  'Long Ball Pass+',
  'Tiki Taka+',
  'Whipped Pass+',
  'First Touch+',
  'Technical+',
  'Trickster+',
  'Press Proven+',
  'Rapid+',
  'Quick Step+',
  'Intercept+',
  'Anticipate+',
  'Slide Tackle+',
  'Bruiser+',
  'Block+',
  'Jockey+',
  'Acrobatic+',
  'Aerial+',
  'Trivela+',
  'Relentless+',
  'Long Throw+',
  'Far Throw+',
  'Footwork+',
  'Cross Claimer+',
  'Rush Out+',
  'Far Reach+',
  'Deflector+',
]

export interface StadiumComboboxProps {
  value?: string
  onChange: (value: string) => void
  options?: string[]
  placeholder?: string
  ariaLabel?: string
  id?: string
  disabled?: boolean
  className?: string
}

export function StadiumCombobox({
  value = '',
  onChange,
  options = DEFAULT_PLAYSTYLES_PLUS,
  placeholder = 'Search PlayStyle+ (e.g. Finesse Shot+)',
  ariaLabel = 'PlayStyle selector',
  id,
  disabled,
  className = '',
}: StadiumComboboxProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState(value)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    setQuery(value)
  }, [value])

  const filteredOptions = useMemo(() => {
    if (!query.trim()) return options
    const q = query.toLowerCase().replace(/\+$/, '').trim()
    return options.filter(opt => opt.toLowerCase().includes(q))
  }, [options, query])

  useEffect(() => {
    if (!isOpen) return
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  function handleSelect(val: string) {
    onChange(val)
    setQuery(val)
    setIsOpen(false)
    inputRef.current?.blur()
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (disabled) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setIsOpen(true)
      setHighlightedIndex(i => (i + 1 < filteredOptions.length ? i + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setIsOpen(true)
      setHighlightedIndex(i => (i - 1 >= 0 ? i - 1 : filteredOptions.length - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (isOpen && filteredOptions[highlightedIndex]) {
        handleSelect(filteredOptions[highlightedIndex])
      }
    } else if (e.key === 'Escape') {
      setIsOpen(false)
    }
  }

  return (
    <div className={`stadium-combobox-wrapper ${className}`} ref={containerRef}>
      <div className="stadium-combobox-input-row">
        <input
          ref={inputRef}
          id={id}
          type="text"
          value={query}
          aria-label={ariaLabel}
          aria-expanded={isOpen}
          aria-autocomplete="list"
          role="combobox"
          placeholder={placeholder}
          disabled={disabled}
          className="stadium-input"
          style={{ paddingRight: query ? '36px' : '16px' }}
          onChange={e => {
            setQuery(e.target.value)
            onChange(e.target.value)
            setIsOpen(true)
            setHighlightedIndex(0)
          }}
          onFocus={() => setIsOpen(true)}
          onKeyDown={handleKeyDown}
        />
        {query && (
          <button
            type="button"
            className="stadium-input-clear-btn"
            onClick={() => {
              setQuery('')
              onChange('')
              inputRef.current?.focus()
            }}
            aria-label="Clear PlayStyle"
          >
            ✕
          </button>
        )}
      </div>

      {isOpen && filteredOptions.length > 0 && (
        <div role="listbox" className="stadium-dropdown-popup">
          {filteredOptions.map((opt, idx) => {
            const isSelected = opt.toLowerCase() === value.toLowerCase()
            const isHighlighted = idx === highlightedIndex
            return (
              <button
                type="button"
                role="option"
                key={opt}
                aria-selected={isSelected}
                className={`stadium-dropdown-option ${isSelected ? 'is-selected' : ''} ${isHighlighted ? 'is-highlighted' : ''}`}
                onClick={() => handleSelect(opt)}
                onMouseEnter={() => setHighlightedIndex(idx)}
              >
                <span className="row gap05 align-center">
                  <span style={{ color: 'var(--accent-gold)' }}>★</span>
                  <span>{opt}</span>
                </span>
                {isSelected && <span className="stadium-dropdown-option-check">✓</span>}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/* ==========================================================================
   5. STADIUM CHECKBOX (Themed & Accessible)
   ========================================================================== */
export interface StadiumCheckboxProps {
  checked: boolean
  onChange: (checked: boolean, e?: React.ChangeEvent<HTMLInputElement>) => void
  label: React.ReactNode
  description?: React.ReactNode
  disabled?: boolean
  id?: string
  ariaLabel?: string
  className?: string
}

export function StadiumCheckbox({
  checked,
  onChange,
  label,
  description,
  disabled,
  id,
  ariaLabel,
  className = '',
}: StadiumCheckboxProps) {
  const generatedId = useId()
  const inputId = id || generatedId

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    if (disabled) return
    if (onChange) onChange(e.target.checked, e)
  }

  return (
    <label
      htmlFor={inputId}
      className={`stadium-checkbox-container ${disabled ? 'is-disabled' : ''} ${className}`}
    >
      <input
        type="checkbox"
        id={inputId}
        checked={checked}
        disabled={disabled}
        aria-label={ariaLabel}
        onChange={handleChange}
        className="stadium-checkbox-input"
      />
      <div className={`stadium-checkbox-box ${checked ? 'is-checked' : ''} ${disabled ? 'is-disabled' : ''}`} aria-hidden="true">
        {checked && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#080D14" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="20 6 9 17 4 12" />
          </svg>
        )}
      </div>
      <div className="stadium-checkbox-text-group">
        <span className="stadium-checkbox-label">{label}</span>
        {description && <span className="stadium-checkbox-desc">{description}</span>}
      </div>
    </label>
  )
}

/* ==========================================================================
   6. STADIUM TACTICAL SELECTOR (Selectable Tactical Cards)
   ========================================================================== */
const TACTIC_METADATA: Record<string, { icon: StadiumIconName; name: string; summary: string }> = {
  BALANCED: { icon: 'sliders', name: 'Balanced', summary: 'Versatile positional discipline' },
  POSSESSION: { icon: 'target', name: 'Possession', summary: 'Ball retention & press resistance' },
  HIGH_PRESS: { icon: 'shield', name: 'High Press', summary: 'Relentless turnovers in attacking third' },
  LOW_BLOCK: { icon: 'shield', name: 'Low Block', summary: 'Rigid containment & box protection' },
  COUNTER_ATTACK: { icon: 'zap', name: 'Counter Attack', summary: 'Explosive vertical transitions' },
  DIRECT_PLAY: { icon: 'arrowRight', name: 'Direct Play', summary: 'Long vertical passing & aerial duels' },
}

export interface StadiumTacticalSelectorProps {
  value: string
  onChange: (tactic: string) => void
  options?: string[]
  id?: string
  ariaLabel?: string
}

export function StadiumTacticalSelector({
  value,
  onChange,
  options = ['BALANCED', 'POSSESSION', 'HIGH_PRESS', 'LOW_BLOCK', 'COUNTER_ATTACK', 'DIRECT_PLAY'],
  id,
  ariaLabel = 'Select tactical system',
}: StadiumTacticalSelectorProps) {
  return (
    <div
      role="radiogroup"
      id={id}
      aria-label={ariaLabel}
      className="stadium-tactical-grid"
    >
      {options.map(tactic => {
        const meta = TACTIC_METADATA[tactic] ?? { icon: 'activity' as StadiumIconName, name: tactic, summary: 'Tactical system' }
        const isActive = value === tactic
        return (
          <button
            key={tactic}
            type="button"
            role="radio"
            aria-checked={isActive}
            className={`stadium-tactical-card ${isActive ? 'is-active' : ''}`}
            onClick={() => onChange(tactic)}
          >
            <span className="stadium-tactical-card-name">
              <StadiumIcon name={meta.icon} size={14} />
              <span>{meta.name}</span>
            </span>
            <span className="stadium-tactical-card-detail">{meta.summary}</span>
          </button>
        )
      })}
    </div>
  )
}
