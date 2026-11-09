
/* WARNING: Globals starting with '_' overlap smaller symbols at the same address */

ulonglong FUN_143d7a390(longlong param_1)

{
  int *piVar1;
  int iVar2;
  uint uVar3;
  code *pcVar4;
  longlong lVar5;
  char cVar6;
  uint uVar7;
  longlong lVar8;
  longlong *plVar9;
  undefined8 uVar10;
  longlong lVar11;
  ulonglong uVar12;
  longlong *plVar13;
  longlong unaff_GS_OFFSET;
  longlong lStack_a8;
  longlong *plStack_a0;
  undefined8 uStack_98;
  undefined8 uStack_90;
  longlong lStack_88;
  undefined8 uStack_80;
  undefined8 uStack_78;
  undefined8 uStack_70;
  undefined8 uStack_68;
  undefined8 uStack_60;
  undefined8 uStack_58;
  undefined8 uStack_50;
  undefined8 uStack_48;
  undefined8 uStack_40;
  undefined4 uStack_38;
  undefined8 uStack_30;
  undefined8 uStack_28;
  
  if ((*(int *)(*(longlong *)(*(longlong *)(unaff_GS_OFFSET + 0x58) + (ulonglong)__tls_index * 8) +
               0x20) < iRam000000014dba8820) &&
     (FUN_140001270(0x14dba8820), iRam000000014dba8820 == -1)) {
    lRam000000014dba8818 = FUN_142bc2b40(&UNK_148d88ba0,&UNK_1490f05d8,0xffffffff,0xff);
    FUN_140001350(0x14dba8820);
  }
  lVar11 = 0;
  lVar8 = lVar11;
  if (DAT_14dba87c8 == '\0') {
    lVar8 = lRam000000014dba8818;
  }
  uStack_98 = 0;
  uStack_90 = 0;
  lStack_88 = 0;
  uStack_80 = 0;
  uStack_78 = _DAT_148a80860;
  uStack_70 = _UNK_148a80868;
  uStack_68 = 0;
  uStack_60 = 0;
  uStack_58 = 0;
  uStack_50 = 0;
  uStack_48 = 0;
  uStack_40 = 0;
  uStack_38 = 0;
  uStack_30 = 0;
  uStack_28 = 0;
  if (lVar8 != 0) {
    FUN_142bc1e50(&uStack_98,0,0xffffffffffffffff,0,0);
  }
  lVar8 = FUN_143d82f90(param_1);
  plVar9 = (longlong *)FUN_1431499a0(param_1,0xffffd8ed);
  uVar12 = plVar9[7];
  if (uVar12 != 0) {
    plVar13 = (longlong *)plVar9[1];
    if (0xf < (ulonglong)plVar13[3]) {
      plVar13 = (longlong *)*plVar13;
    }
    if (*(code **)(lVar8 + 0x38) != (code *)0x0) {
      uVar10 = (**(code **)(lVar8 + 0x38))
                         (*(undefined8 *)(lVar8 + 0x30),*(undefined8 *)(lVar8 + 0x20));
      *(undefined8 *)(lVar8 + 0x30) = uVar10;
      *(undefined8 *)(lVar8 + 0x38) = 0;
    }
    if ((*(ulonglong *)(lVar8 + 0x30) & uVar12) != uVar12) {
      FUN_142ab4c10(~*(ulonglong *)(lVar8 + 0x30) & uVar12,&UNK_148a74874,plVar13,0);
    }
  }
  if (DAT_14dba87c8 == '\0') {
    FUN_143d7feb0(*(undefined8 *)(plVar9[6] + 8),plVar9[1]);
  }
  lStack_a8 = 0;
  plStack_a0 = (longlong *)0x0;
  cVar6 = FUN_143d81a90(param_1,1,&lStack_a8);
  lVar5 = lStack_a8;
  if (((cVar6 == '\0') || (lStack_a8 == 0)) ||
     (cVar6 = func_0x000142abb820(plVar9,lStack_a8), cVar6 == '\0')) {
    uVar10 = func_0x0001407c7020(plVar9[1]);
    FUN_143a7c550(&UNK_1490f05e0,uVar10);
    pcVar4 = (code *)swi(3);
    uVar12 = (*pcVar4)();
    return uVar12;
  }
  if ((char)plVar9[10] == '\0') {
    if ((*(longlong *)(*(longlong *)(lVar5 + 0x18) + 400) == 0) && (*(char *)(lVar5 + 0xbb) == '\0')
       ) goto code_r0x000143d7a578;
    uVar10 = 0;
  }
  else {
    if ((*(char *)(*(longlong *)(lVar5 + 0x18) + 400) == '\0') && (*(char *)(lVar5 + 0xbb) == '\0'))
    goto code_r0x000143d7a578;
    uVar10 = 1;
  }
  FUN_142b39c90(lVar5,lVar8,uVar10);
code_r0x000143d7a578:
  FUN_143d78ad0(param_1,lVar5,plVar9);
  lVar8 = lVar11;
  if (param_1 != 0) {
    lVar8 = func_0x0001409ed100(param_1);
  }
  if (*(char *)(lVar8 + 0xa9) != '\0') {
    FUN_143d7a1b0(param_1,lVar5,plVar9);
  }
  if (DAT_14dc2baf8 == '\0') {
    lVar8 = lVar11;
    if (param_1 != 0) {
      lVar8 = func_0x0001409ed100(param_1);
    }
    cVar6 = *(char *)(lVar8 + 0xaa);
  }
  else {
    cVar6 = FUN_147963030();
  }
  if (cVar6 != '\0') {
    FUN_143d7b5f0(param_1,lVar5,plVar9);
  }
  if ((int)plVar9[0x11] == 1) {
    uVar7 = (**(code **)(*plVar9 + 8))();
  }
  else {
    uVar7 = (**(code **)(*plVar9 + 0x10))(plVar9,lVar5,param_1,1);
  }
  if (DAT_14d5077b8 != '\0') {
    uVar3 = *(uint *)((longlong)plVar9 + 0x44);
    if (param_1 != 0) {
      lVar11 = func_0x0001409ed100(param_1);
    }
    if (*(longlong *)(lVar11 + 0xb0) != 0) {
      piVar1 = (int *)(*(longlong *)(lVar11 + 0xb0) + (ulonglong)uVar3 * 4);
      *piVar1 = *piVar1 + 1;
    }
  }
  func_0x000143d507c0(param_1,plVar9,0);
  plVar9 = plStack_a0;
  if (plStack_a0 != (longlong *)0x0) {
    LOCK();
    plVar13 = plStack_a0 + 1;
    lVar8 = *plVar13;
    *(int *)plVar13 = (int)*plVar13 + -1;
    UNLOCK();
    if ((int)lVar8 == 1) {
      (**(code **)*plStack_a0)(plStack_a0);
      LOCK();
      piVar1 = (int *)((longlong)plVar9 + 0xc);
      iVar2 = *piVar1;
      *piVar1 = *piVar1 + -1;
      UNLOCK();
      if (iVar2 == 1) {
        (**(code **)(*plStack_a0 + 8))();
      }
    }
  }
  if (lStack_88 != 0) {
    FUN_142bc3320(&uStack_98,0xffffffffffffffff);
  }
  return (ulonglong)uVar7;
}

