
undefined8 FUN_143d6e4c0(undefined8 param_1)

{
  int iVar1;
  longlong *plVar2;
  undefined8 uVar3;
  longlong lVar4;
  undefined8 uVar5;
  code *pcVar6;
  undefined *puVar7;
  
  plVar2 = (longlong *)FUN_143149a10(param_1,1,uRam000000014dba8638);
  if (plVar2 == (longlong *)0x0) {
    FUN_14314de00(param_1,1,uRam000000014caee360);
    pcVar6 = (code *)swi(3);
    uVar3 = (*pcVar6)();
    return uVar3;
  }
  uVar3 = FUN_14314ce10(param_1,2);
  lVar4 = FUN_142ab00e0(*plVar2,uVar3);
  if (lVar4 == 0) {
    iVar1 = func_0x0001478c035c(uVar3,&UNK_1490eee20);
    if (iVar1 == 0) {
      puVar7 = &UNK_1490eee20;
      pcVar6 = FUN_143d6ec40;
    }
    else {
      iVar1 = func_0x0001478c035c(uVar3,&UNK_1490eee30);
      if (iVar1 == 0) {
        puVar7 = &UNK_1490eee30;
        pcVar6 = FUN_143d6e210;
      }
      else {
        iVar1 = func_0x0001478c035c(uVar3,&UNK_1490eee40);
        if (iVar1 != 0) {
          uVar5 = func_0x0001407c7020(*(undefined8 *)(*plVar2 + 8));
          FUN_143a7c550(&UNK_1490eee50,uVar3,uVar5);
          pcVar6 = (code *)swi(3);
          uVar3 = (*pcVar6)();
          return uVar3;
        }
        puVar7 = &UNK_1490eee40;
        pcVar6 = FUN_143d6e2c0;
      }
    }
    FUN_143146a90(param_1,pcVar6,puVar7,0,0);
  }
  else {
    FUN_14097d090(param_1,lVar4);
  }
  return 1;
}

