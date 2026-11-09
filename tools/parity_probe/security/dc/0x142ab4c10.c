
void FUN_142ab4c10(ulonglong param_1,undefined *param_2,longlong param_3,char param_4)

{
  code *pcVar1;
  ulonglong uVar2;
  undefined *puStackX_8;
  undefined *puStackX_10;
  longlong lStackX_18;
  undefined8 auStack_38 [2];

  lStackX_18 = param_3;
  if ((param_1 & 0x8000) != 0) {
    FUN_142ab49b0(param_2,param_3);
  }
  uVar2 = param_1 & 0x3fffffffff0b00;
  if (uVar2 != 0) {
    FUN_142ab4760(uVar2,param_2,param_3);
  }
  puStackX_10 = &UNK_148d756e0;
  if ((param_1 & 0x8000) != 0) {
    if (param_2 != (undefined *)0x0) {
      puStackX_10 = param_2;
    }
    uVar2 = uVar2 - (uVar2 >> 1 & 0x5555555555555555);
    uVar2 = (uVar2 >> 2 & 0x3333333333333333) + (uVar2 & 0x3333333333333333);
    if ((char)(((uVar2 >> 4) + uVar2 & 0xf0f0f0f0f0f0f0f) * 0x101010101010101 >> 0x38) != '\0') {
      if (param_3 != 0) {
        FUN_142ab2a80(&UNK_148d75700,&puStackX_10,&lStackX_18,&lStackX_18);
        pcVar1 = (code *)swi(3);
        (*pcVar1)();
        return;
      }
      FUN_140cf9760(&UNK_148d75780,&puStackX_10);
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
    if (param_3 != 0) {
      FUN_142ab2a10(&UNK_148d75800,&puStackX_10,&lStackX_18);
      pcVar1 = (code *)swi(3);
      (*pcVar1)();
      return;
    }
    FUN_140cf9760(&UNK_148d75860,&puStackX_10);
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  if (param_2 != (undefined *)0x0) {
    puStackX_10 = param_2;
  }
  puStackX_8 = &UNK_148d758d8;
  if (param_4 != '\0') {
    puStackX_8 = &UNK_148d758c0;
  }
  auStack_38[0] = func_0x000142ab2f20(param_1);
  if (param_3 != 0) {
    FUN_142ab2af0(&UNK_148d758f0,&puStackX_10,&lStackX_18,&puStackX_8,auStack_38);
    pcVar1 = (code *)swi(3);
    (*pcVar1)();
    return;
  }
  FUN_142ab2a80(&UNK_148d75920,&puStackX_10,&puStackX_8,auStack_38);
  pcVar1 = (code *)swi(3);
  (*pcVar1)();
  return;
}
