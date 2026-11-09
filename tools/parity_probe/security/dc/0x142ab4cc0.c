
void FUN_142ab4cc0(longlong param_1,undefined8 param_2)

{
  code *pcVar1;
  longlong in_RAX;
  longlong unaff_RBX;

  if ((char)((in_RAX + param_1 & 0xf0f0f0f0f0f0f0fU) * 0x101010101010101 >> 0x38) == '\0') {
    if (unaff_RBX != 0) {
      FUN_142ab2a10(&UNK_148d75800,param_2,&stack0x00000080);
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
    FUN_140cf9760(&UNK_148d75860);
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  if (unaff_RBX != 0) {
    FUN_142ab2a80(&UNK_148d75700,param_2,&stack0x00000080,&stack0x00000080);
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  FUN_140cf9760(&UNK_148d75780);
  pcVar1 = (code *)swi(3);
  (*pcVar1)();
  return;
}
