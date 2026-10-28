"use client";

import { EditorContent, useEditor } from "@tiptap/react";

import { MinutaFormatToolbar } from "@/components/admins/minuta-format-toolbar";
import {
  createDocumentEditorExtensions,
  DOCUMENT_EDITOR_PROSE_CLASS,
} from "@/lib/tiptap/document-editor-extensions";
import {
  DOCUMENT_PAGE_SCROLL_CLASS,
  DOCUMENT_PAGE_SHEET_CLASS,
} from "@/lib/tiptap/document-page-layout";

export function MinutaEditor({
  value,
  tokens,
  onChange,
}: {
  value: string;
  tokens: { key: string }[];
  onChange: (html: string) => void;
}) {
  const editor = useEditor({
    extensions: createDocumentEditorExtensions(),
    content: value || "<p></p>",
    immediatelyRender: false,
    shouldRerenderOnTransaction: true,
    onUpdate: ({ editor: current }) => onChange(current.getHTML()),
    editorProps: {
      attributes: {
        class: DOCUMENT_EDITOR_PROSE_CLASS,
      },
    },
  });

  return (
    <div className="overflow-hidden rounded-lg border border-input bg-background">
      <MinutaFormatToolbar editor={editor} tokens={tokens.map((token) => token.key)} />
      <div className={DOCUMENT_PAGE_SCROLL_CLASS}>
        <div role="document" aria-label="A4" className={DOCUMENT_PAGE_SHEET_CLASS}>
          <EditorContent editor={editor} />
        </div>
      </div>
    </div>
  );
}
