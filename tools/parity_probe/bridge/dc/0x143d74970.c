
ulonglong FUN_143d74970(longlong param_1,longlong *param_2,undefined8 param_3,longlong *param_4)

{
  int *piVar1;
  char cVar2;
  int iVar3;
  uint uVar4;
  longlong lVar5;
  longlong lVar6;
  undefined8 uVar7;
  longlong lVar8;
  undefined8 uVar9;
  ulonglong uVar10;
  code *pcVar11;
  longlong *plVar12;
  longlong lStack_28;
  longlong lStack_20;
  
  iVar3 = (int)param_4[1];
  if (iVar3 == 0) {
    lVar8 = *param_4;
    if ((*(uint *)(lVar8 + 0xa4) >> 4 & 1) == 0) {
      return 0;
    }
    FUN_143d78ce0(param_1,lVar8);
    lVar6 = 0;
    lVar5 = lVar6;
    if (param_1 != 0) {
      lVar5 = func_0x0001409ed100(param_1);
    }
    if (*(char *)(lVar5 + 0xa9) != '\0') {
      FUN_143d7a250(param_1,lVar8);
    }
    lStack_20 = *param_2;
    lStack_28 = lVar8;
    FUN_143d80280(&lStack_28,param_1,param_3);
    if (cRam000000014dbcd580 != '\0') {
      *(longlong *)(lVar8 + 0x50) = *(longlong *)(lVar8 + 0x50) + 1;
    }
    if (DAT_14d5077b8 != '\0') {
      uVar4 = *(uint *)(lVar8 + 0x44);
      if (param_1 != 0) {
        lVar6 = func_0x0001409ed100(param_1);
      }
      if (*(longlong *)(lVar6 + 0xb0) != 0) {
        piVar1 = (int *)(*(longlong *)(lVar6 + 0xb0) + (ulonglong)uVar4 * 4);
        *piVar1 = *piVar1 + 1;
      }
    }
  }
  else {
    if (iVar3 == 1) {
      lVar8 = *param_4;
      lVar6 = 0;
      lVar5 = lVar6;
      if (param_1 != 0) {
        lVar5 = func_0x0001409ed100(param_1);
      }
      lVar5 = *(longlong *)(*(longlong *)(*(longlong *)(lVar5 + 0x18) + 0x30) + 0x128);
      if ((lVar5 != 0) && (*(char *)(lVar5 + 0x565) != '\0')) {
        uVar7 = func_0x0001407c7020(*(undefined8 *)(lVar8 + 8));
        uVar9 = func_0x0001407c7020(*(undefined8 *)(*(longlong *)(lVar8 + 0x30) + 8));
        FUN_143a7c550(&UNK_1490f02e8,uVar9,uVar7);
        pcVar11 = (code *)swi(3);
        uVar10 = (*pcVar11)();
        return uVar10;
      }
      lVar5 = lVar6;
      if (param_1 != 0) {
        lVar5 = func_0x0001409ed100(param_1);
      }
      if (*(char *)(lVar5 + 0xa9) != '\0') {
        FUN_143d7a110(param_1,lVar8);
      }
      if (DAT_14dc2baf8 == '\0') {
        if (param_1 != 0) {
          lVar6 = func_0x0001409ed100(param_1);
        }
        cVar2 = *(char *)(lVar6 + 0xaa);
      }
      else {
        cVar2 = FUN_147963030();
      }
      if (cVar2 != '\0') {
        FUN_143d7b560(param_1,lVar8);
      }
      lVar5 = param_2[1];
      lStack_28 = 0;
      lStack_20 = 0;
      if (lVar5 != 0) {
        lStack_28 = *param_2;
        LOCK();
        *(int *)(lVar5 + 0xc) = *(int *)(lVar5 + 0xc) + 1;
        UNLOCK();
        lStack_20 = lVar5;
      }
      uVar4 = FUN_143d7c430(&lStack_28,lVar8,param_3,param_1);
      func_0x000143d507c0(param_1,lVar8,0);
      return (ulonglong)uVar4;
    }
    if (iVar3 == 2) {
      lVar8 = *param_4;
      lVar6 = 0;
      lVar5 = lVar6;
      if (param_1 != 0) {
        lVar5 = func_0x0001409ed100(param_1);
      }
      if (*(char *)(lVar5 + 0xa9) != '\0') {
        FUN_143d7a1b0(param_1,*param_2,lVar8);
      }
      if (DAT_14dc2baf8 == '\0') {
        if (param_1 != 0) {
          lVar6 = func_0x0001409ed100(param_1);
        }
        cVar2 = *(char *)(lVar6 + 0xaa);
      }
      else {
        cVar2 = FUN_147963030();
      }
      if (cVar2 != '\0') {
        FUN_143d7b5f0(param_1,*param_2,lVar8);
      }
      FUN_143d78ad0(param_1,*param_2,lVar8);
      FUN_1431470b0(param_1,lVar8,0);
      FUN_143147ab0(param_1,0xffffd8ef);
      iVar3 = FUN_143149af0(param_1,0xffffffff);
      if (iVar3 != 0) goto code_r0x000143d74d2e;
      FUN_143148fa0(param_1,0xfffffffe);
      FUN_1431470b0(param_1,lVar8,0);
      plVar12 = *(longlong **)(lVar8 + 8);
      if (0xf < (ulonglong)plVar12[3]) {
        plVar12 = (longlong *)*plVar12;
      }
      pcVar11 = FUN_143d7a390;
    }
    else {
      if (iVar3 != 3) {
        if (iVar3 != 4) {
          return 0;
        }
        uVar7 = func_0x0001407c7020(*(undefined8 *)(*param_4 + 8));
        lVar8 = func_0x0001407d5810(param_2);
        uVar9 = func_0x0001407c7020(*(undefined8 *)(*(longlong *)(lVar8 + 0x18) + 8));
        FUN_143a7c550(&UNK_1490f0720,uVar7,uVar9);
        pcVar11 = (code *)swi(3);
        uVar10 = (*pcVar11)();
        return uVar10;
      }
      lVar8 = *param_4;
      FUN_143d78ad0(param_1,*param_2,lVar8);
      lVar6 = 0;
      lVar5 = lVar6;
      if (param_1 != 0) {
        lVar5 = func_0x0001409ed100(param_1);
      }
      if (*(char *)(lVar5 + 0xa9) != '\0') {
        FUN_143d7a1b0(param_1,*param_2,lVar8);
      }
      if (DAT_14dc2baf8 == '\0') {
        if (param_1 != 0) {
          lVar6 = func_0x0001409ed100(param_1);
        }
        cVar2 = *(char *)(lVar6 + 0xaa);
      }
      else {
        cVar2 = FUN_147963030();
      }
      if (cVar2 != '\0') {
        FUN_143d7b5f0(param_1,*param_2,lVar8);
      }
      FUN_1431470b0(param_1,lVar8,0);
      FUN_143147ab0(param_1,0xffffd8ef);
      iVar3 = FUN_143149af0(param_1,0xffffffff);
      if (iVar3 != 0) goto code_r0x000143d74d2e;
      FUN_143148fa0(param_1,0xfffffffe);
      FUN_1431470b0(param_1,lVar8,0);
      plVar12 = *(longlong **)(lVar8 + 8);
      if (0xf < (ulonglong)plVar12[3]) {
        plVar12 = (longlong *)*plVar12;
      }
      pcVar11 = FUN_143d7ab30;
    }
    FUN_143146a90(param_1,pcVar11,plVar12,1,0);
    FUN_1431470b0(param_1,lVar8,0);
    FUN_143147730(param_1,0xfffffffe);
    FUN_143148f30(param_1,0xffffd8ef);
  }
code_r0x000143d74d2e:
  func_0x000143d507c0(param_1,lVar8,0);
  return 1;
}

