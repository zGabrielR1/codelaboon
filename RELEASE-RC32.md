# RC32 ? Fix opening Windows tasks in Oh My Pi

Opening a web task in Oh My Pi on Windows now uses OMP-compatible session paths. Drive colons and path separators are encoded before writing the imported conversation.

This release adds an offline regression test for a Windows drive path and verifies that the imported transcript can be read back.
