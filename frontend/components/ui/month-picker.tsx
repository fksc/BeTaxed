"use client"

import { format, isValid, parse } from "date-fns"
import { enUS, pt } from "date-fns/locale"
import { useLocale } from "next-intl"

import { cn } from "@/lib/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

const MONTH_VALUES = [
  "01",
  "02",
  "03",
  "04",
  "05",
  "06",
  "07",
  "08",
  "09",
  "10",
  "11",
  "12",
] as const

function yearsAround(center: number): string[] {
  const years: string[] = []
  for (let year = center - 6; year <= center + 1; year += 1) {
    years.push(String(year))
  }
  return years
}

function parts(value: string): { year: string; month: string } {
  const parsed = parse(value.slice(0, 7), "yyyy-MM", new Date())
  if (isValid(parsed)) {
    return { year: format(parsed, "yyyy"), month: format(parsed, "MM") }
  }
  const now = new Date()
  return {
    year: String(now.getFullYear()),
    month: String(now.getMonth() + 1).padStart(2, "0"),
  }
}

export function MonthPicker({
  value,
  onChange,
  className,
  id,
  disabled,
}: {
  value: string
  onChange: (next: string) => void
  className?: string
  id?: string
  disabled?: boolean
}) {
  const locale = useLocale()
  const dateLocale = locale === "pt" ? pt : enUS
  const { year, month } = parts(value)
  const years = yearsAround(Number(year))

  return (
    <div id={id} className={cn("flex gap-2", className)}>
      <Select
        value={month}
        disabled={disabled}
        items={Object.fromEntries(
          MONTH_VALUES.map((item, index) => [
            item,
            format(new Date(2000, index, 1), "MMMM", { locale: dateLocale }),
          ]),
        )}
        onValueChange={(next) => {
          if (next) {
            onChange(`${year}-${next}`)
          }
        }}
      >
        <SelectTrigger className="min-w-36 flex-1" aria-label={locale === "pt" ? "Mês" : "Month"}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MONTH_VALUES.map((item, index) => (
            <SelectItem key={item} value={item}>
              {format(new Date(2000, index, 1), "MMMM", { locale: dateLocale })}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      <Select
        value={year}
        disabled={disabled}
        items={Object.fromEntries(years.map((item) => [item, item]))}
        onValueChange={(next) => {
          if (next) {
            onChange(`${next}-${month}`)
          }
        }}
      >
        <SelectTrigger className="w-[5.75rem]" aria-label={locale === "pt" ? "Ano" : "Year"}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {years.map((item) => (
            <SelectItem key={item} value={item}>
              {item}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  )
}
