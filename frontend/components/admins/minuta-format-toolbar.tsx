"use client";

import type { Editor } from "@tiptap/react";
import {
  AlignCenter,
  AlignJustify,
  AlignLeft,
  AlignRight,
  Bold,
  Braces,
  Code,
  Columns2,
  Heading1,
  Heading2,
  Heading3,
  Highlighter,
  ImageIcon,
  Italic,
  Link2,
  List,
  ListOrdered,
  Minus,
  Palette,
  Pilcrow,
  Quote,
  Redo2,
  Strikethrough,
  Subscript,
  Superscript,
  Underline,
  Undo2,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

const FONT_SIZES = ["10px", "12px", "14px", "16px", "18px", "20px", "24px", "28px", "32px"] as const;

const TEXT_COLORS = [
  { value: "", swatch: "bg-foreground", key: "colorDefault" },
  { value: "#111827", swatch: "bg-neutral-900", key: "colorBlack" },
  { value: "#b91c1c", swatch: "bg-red-700", key: "colorRed" },
  { value: "#b45309", swatch: "bg-amber-700", key: "colorAmber" },
  { value: "#1d4ed8", swatch: "bg-blue-700", key: "colorBlue" },
  { value: "#15803d", swatch: "bg-green-700", key: "colorGreen" },
] as const;

const HIGHLIGHTS = [
  { value: "", swatch: "bg-transparent ring-1 ring-border", key: "highlightNone" },
  { value: "#fef08a", swatch: "bg-yellow-200", key: "highlightYellow" },
  { value: "#bbf7d0", swatch: "bg-green-200", key: "highlightGreen" },
  { value: "#bfdbfe", swatch: "bg-blue-200", key: "highlightBlue" },
  { value: "#fbcfe8", swatch: "bg-pink-200", key: "highlightPink" },
] as const;

function ToolButton({
  label,
  pressed,
  disabled,
  onClick,
  children,
}: {
  label: string;
  pressed?: boolean;
  disabled?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <Button
            type="button"
            variant={pressed ? "secondary" : "ghost"}
            size="icon-sm"
            aria-pressed={pressed}
            aria-label={label}
            disabled={disabled}
            onClick={onClick}
          />
        }
      >
        {children}
      </TooltipTrigger>
      <TooltipContent side="bottom">{label}</TooltipContent>
    </Tooltip>
  );
}

export function MinutaFormatToolbar({
  editor,
  tokens,
}: {
  editor: Editor | null;
  tokens: readonly string[];
}) {
  const t = useTranslations("admins.editor");
  if (!editor) return null;

  const fontSize = (editor.getAttributes("textStyle").fontSize as string | undefined) ?? "";

  return (
    <div
      className="flex flex-wrap items-center gap-0.5 border-b bg-muted/30 p-1"
      role="toolbar"
      aria-label={t("toolbarAria")}
    >
      <ToolButton
        label={t("undo")}
        disabled={!editor.can().undo()}
        onClick={() => editor.chain().focus().undo().run()}
      >
        <Undo2 />
      </ToolButton>
      <ToolButton
        label={t("redo")}
        disabled={!editor.can().redo()}
        onClick={() => editor.chain().focus().redo().run()}
      >
        <Redo2 />
      </ToolButton>

      <Separator orientation="vertical" className="mx-1 h-6" />

      <ToolButton
        label={t("paragraph")}
        pressed={editor.isActive("paragraph") && !editor.isActive("heading")}
        onClick={() => editor.chain().focus().setParagraph().run()}
      >
        <Pilcrow />
      </ToolButton>
      <ToolButton
        label={t("heading1")}
        pressed={editor.isActive("heading", { level: 1 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
      >
        <Heading1 />
      </ToolButton>
      <ToolButton
        label={t("heading2")}
        pressed={editor.isActive("heading", { level: 2 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
      >
        <Heading2 />
      </ToolButton>
      <ToolButton
        label={t("heading3")}
        pressed={editor.isActive("heading", { level: 3 })}
        onClick={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}
      >
        <Heading3 />
      </ToolButton>

      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button type="button" variant="ghost" size="sm" className="h-7 px-2 text-xs" aria-label={t("fontSize")} />
          }
        >
          {fontSize || t("fontSizeShort")}
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-28">
          <DropdownMenuRadioGroup
            value={fontSize}
            onValueChange={(value) => {
              if (!value) editor.chain().focus().unsetFontSize().run();
              else editor.chain().focus().setFontSize(value).run();
            }}
          >
            <DropdownMenuRadioItem value="">{t("fontSizeDefault")}</DropdownMenuRadioItem>
            {FONT_SIZES.map((size) => (
              <DropdownMenuRadioItem key={size} value={size}>
                {size}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <Separator orientation="vertical" className="mx-1 h-6" />

      <ToolButton
        label={t("bold")}
        pressed={editor.isActive("bold")}
        onClick={() => editor.chain().focus().toggleBold().run()}
      >
        <Bold />
      </ToolButton>
      <ToolButton
        label={t("italic")}
        pressed={editor.isActive("italic")}
        onClick={() => editor.chain().focus().toggleItalic().run()}
      >
        <Italic />
      </ToolButton>
      <ToolButton
        label={t("underline")}
        pressed={editor.isActive("underline")}
        onClick={() => editor.chain().focus().toggleUnderline().run()}
      >
        <Underline />
      </ToolButton>
      <ToolButton
        label={t("strike")}
        pressed={editor.isActive("strike")}
        onClick={() => editor.chain().focus().toggleStrike().run()}
      >
        <Strikethrough />
      </ToolButton>
      <ToolButton
        label={t("subscript")}
        pressed={editor.isActive("subscript")}
        onClick={() => editor.chain().focus().toggleSubscript().run()}
      >
        <Subscript />
      </ToolButton>
      <ToolButton
        label={t("superscript")}
        pressed={editor.isActive("superscript")}
        onClick={() => editor.chain().focus().toggleSuperscript().run()}
      >
        <Superscript />
      </ToolButton>
      <ToolButton
        label={t("code")}
        pressed={editor.isActive("code")}
        onClick={() => editor.chain().focus().toggleCode().run()}
      >
        <Code />
      </ToolButton>

      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button type="button" variant="ghost" size="icon-sm" aria-label={t("textColor")} />}
        >
          <Palette />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-36">
          {TEXT_COLORS.map((color) => (
            <DropdownMenuItem
              key={color.key}
              onClick={() => {
                if (!color.value) editor.chain().focus().unsetColor().run();
                else editor.chain().focus().setColor(color.value).run();
              }}
            >
              <span className={`size-3 rounded-full ${color.swatch}`} />
              {t(color.key)}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button type="button" variant="ghost" size="icon-sm" aria-label={t("highlight")} />}
        >
          <Highlighter />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-36">
          {HIGHLIGHTS.map((color) => (
            <DropdownMenuItem
              key={color.key}
              onClick={() => {
                if (!color.value) editor.chain().focus().unsetHighlight().run();
                else editor.chain().focus().setHighlight({ color: color.value }).run();
              }}
            >
              <span className={`size-3 rounded-sm ${color.swatch}`} />
              {t(color.key)}
            </DropdownMenuItem>
          ))}
        </DropdownMenuContent>
      </DropdownMenu>

      <Separator orientation="vertical" className="mx-1 h-6" />

      <ToolButton
        label={t("alignLeft")}
        pressed={editor.isActive({ textAlign: "left" })}
        onClick={() => editor.chain().focus().setTextAlign("left").run()}
      >
        <AlignLeft />
      </ToolButton>
      <ToolButton
        label={t("alignCenter")}
        pressed={editor.isActive({ textAlign: "center" })}
        onClick={() => editor.chain().focus().setTextAlign("center").run()}
      >
        <AlignCenter />
      </ToolButton>
      <ToolButton
        label={t("alignRight")}
        pressed={editor.isActive({ textAlign: "right" })}
        onClick={() => editor.chain().focus().setTextAlign("right").run()}
      >
        <AlignRight />
      </ToolButton>
      <ToolButton
        label={t("alignJustify")}
        pressed={editor.isActive({ textAlign: "justify" })}
        onClick={() => editor.chain().focus().setTextAlign("justify").run()}
      >
        <AlignJustify />
      </ToolButton>

      <Separator orientation="vertical" className="mx-1 h-6" />

      <ToolButton
        label={t("bulletList")}
        pressed={editor.isActive("bulletList")}
        onClick={() => editor.chain().focus().toggleBulletList().run()}
      >
        <List />
      </ToolButton>
      <ToolButton
        label={t("orderedList")}
        pressed={editor.isActive("orderedList")}
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
      >
        <ListOrdered />
      </ToolButton>
      <ToolButton
        label={t("quote")}
        pressed={editor.isActive("blockquote")}
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
      >
        <Quote />
      </ToolButton>
      <ToolButton
        label={t("divider")}
        onClick={() => editor.chain().focus().setHorizontalRule().run()}
      >
        <Minus />
      </ToolButton>

      <DropdownMenu>
        <DropdownMenuTrigger
          render={<Button type="button" variant="ghost" size="icon-sm" aria-label={t("columns")} />}
        >
          <Columns2 />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="min-w-64">
          <DropdownMenuLabel>{t("columnsTitle")}</DropdownMenuLabel>
          <DropdownMenuItem
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 12, cols: 2, withHeaderRow: false }).run()
            }
          >
            {t("insertColumns")}
          </DropdownMenuItem>
          <DropdownMenuItem
            onClick={() =>
              editor.chain().focus().insertTable({ rows: 11, cols: 2, withHeaderRow: true }).run()
            }
          >
            {t("insertColumnsHeader")}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            disabled={!editor.can().addRowAfter()}
            onClick={() => editor.chain().focus().addRowAfter().run()}
          >
            {t("addRow")}
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!editor.can().deleteRow()}
            onClick={() => editor.chain().focus().deleteRow().run()}
          >
            {t("deleteRow")}
          </DropdownMenuItem>
          <DropdownMenuItem
            disabled={!editor.can().deleteTable()}
            onClick={() => editor.chain().focus().deleteTable().run()}
          >
            {t("deleteTable")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <ToolButton
        label={t("link")}
        pressed={editor.isActive("link")}
        onClick={() => {
          const previous = (editor.getAttributes("link").href as string | undefined) ?? "";
          const next = window.prompt(t("linkPrompt"), previous);
          if (next === null) return;
          if (next === "") {
            editor.chain().focus().extendMarkRange("link").unsetLink().run();
            return;
          }
          editor.chain().focus().extendMarkRange("link").setLink({ href: next }).run();
        }}
      >
        <Link2 />
      </ToolButton>
      <ToolButton
        label={t("image")}
        onClick={() => {
          const src = window.prompt(t("imagePrompt"));
          if (!src) return;
          editor.chain().focus().setImage({ src }).run();
        }}
      >
        <ImageIcon />
      </ToolButton>

      {tokens.length > 0 ? (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button type="button" variant="ghost" size="sm" className="h-7 gap-1 px-2 text-xs" />}
          >
            <Braces className="size-3.5" />
            {t("insertVariable")}
          </DropdownMenuTrigger>
          <DropdownMenuContent className="max-h-72 min-w-52">
            {tokens.map((token) => (
              <DropdownMenuItem
                key={token}
                onClick={() => editor.chain().focus().insertContent(`{{ ${token} }}`).run()}
              >
                <span className="font-mono text-xs">{`{{ ${token} }}`}</span>
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ) : null}
    </div>
  );
}
