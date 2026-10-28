import type { Extensions } from "@tiptap/core";
import Color from "@tiptap/extension-color";
import Highlight from "@tiptap/extension-highlight";
import Image from "@tiptap/extension-image";
import Subscript from "@tiptap/extension-subscript";
import Superscript from "@tiptap/extension-superscript";
import { Table, TableKit } from "@tiptap/extension-table";
import TextAlign from "@tiptap/extension-text-align";
import { TextStyle } from "@tiptap/extension-text-style";
import Typography from "@tiptap/extension-typography";
import Underline from "@tiptap/extension-underline";
import StarterKit from "@tiptap/starter-kit";

import { FontSize } from "@/lib/tiptap/font-size-extension";
import { cn } from "@/lib/utils";

const MinutaTable = Table.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      borderless: {
        default: false,
        parseHTML: (element: HTMLElement) => element.classList.contains("borderless"),
        renderHTML: (attributes: { borderless?: boolean }) =>
          attributes.borderless ? { class: "borderless" } : {},
      },
    };
  },
});

export function createDocumentEditorExtensions(): Extensions {
  return [
    StarterKit.configure({
      underline: false,
      link: {
        openOnClick: false,
        autolink: false,
        HTMLAttributes: {
          class: "text-primary underline underline-offset-2 font-medium",
        },
      },
    }),
    Underline,
    Subscript,
    Superscript,
    TextStyle,
    FontSize,
    Color,
    Highlight.configure({ multicolor: true }),
    TextAlign.configure({
      types: ["heading", "paragraph"],
    }),
    Typography,
    Image.configure({
      inline: false,
      allowBase64: true,
      HTMLAttributes: {
        class: "max-w-full h-auto rounded-md",
      },
    }),
    MinutaTable.configure({
      resizable: false,
      HTMLAttributes: {
        class: "w-full table-fixed border-collapse text-sm",
      },
    }),
    TableKit.configure({
      table: false,
      tableCell: {
        HTMLAttributes: {
          class:
            "border border-border align-top p-3 text-[15px] leading-relaxed [&_p]:my-2 [&_p:first-child]:mt-0",
        },
      },
      tableHeader: {
        HTMLAttributes: {
          class:
            "border border-border bg-muted/60 p-3 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground [&_p]:m-0",
        },
      },
    }),
  ];
}

export const DOCUMENT_EDITOR_PROSE_CLASS = cn(
  "min-h-[257mm] w-full outline-none",
  "[&_p]:my-2 [&_p:first-child]:mt-0",
  "[&_h1]:mt-5 [&_h1]:mb-3 [&_h1]:text-2xl [&_h1]:font-bold",
  "[&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:text-xl [&_h2]:font-semibold",
  "[&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:text-lg [&_h3]:font-semibold",
  "[&_blockquote]:border-l-4 [&_blockquote]:border-border [&_blockquote]:pl-4 [&_blockquote]:italic",
  "[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-[0.9em]",
  "[&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:border [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs",
  "[&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-6",
  "[&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-6",
  "[&_hr]:my-6 [&_hr]:border-border",
  "[&_img]:my-4 [&_img]:h-auto [&_img]:max-w-full [&_img]:rounded-md",
  "[&_mark]:rounded-sm [&_mark]:px-0.5",
  "[&_sub]:align-sub [&_sub]:text-[0.75em]",
  "[&_sup]:align-super [&_sup]:text-[0.75em]",
  "[&_td]:align-top [&_th]:align-middle",
  "[&_table.borderless_td]:border-0 [&_table.borderless_th]:border-0",
  "[&_.tableWrapper]:my-4 [&_.tableWrapper]:max-w-full [&_.tableWrapper]:overflow-x-auto",
  "[&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2",
);
