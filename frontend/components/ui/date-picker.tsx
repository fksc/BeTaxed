"use client"

import { format, isValid, parse } from "date-fns"
import { CalendarIcon } from "lucide-react"

import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

function parseValue(value: string): Date | undefined {
  const parsed = parse(value, "yyyy-MM-dd", new Date())
  return isValid(parsed) ? parsed : undefined
}

export function DatePicker({
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
  const selected = parseValue(value)

  return (
    <Popover>
      <PopoverTrigger
        disabled={disabled}
        render={
          <Button
            id={id}
            type="button"
            variant="outline"
            disabled={disabled}
            className={cn(
              "w-full justify-between font-normal data-[empty=true]:text-muted-foreground",
              className
            )}
            data-empty={!selected}
          />
        }
      >
        <span className="truncate">
          {selected ? format(selected, "dd/MM/yyyy") : "—"}
        </span>
        <CalendarIcon className="size-4 text-muted-foreground" />
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(date) => {
            if (!date) {
              return
            }
            onChange(format(date, "yyyy-MM-dd"))
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
