""" Test setups """


# This dict specifies all the instruments and setups that are supported by the dev suite.
#  The keys are the instruments and the values are a list of the supported setups.
all_setups = {
        'bok_bc': ['300','600'],
    'gemini_gnirs_echelle': ['32_SB_SXD', '10_LB_SXD'],
    'gemini_gnirs_ifu': ['LR_IFU_32mm'],
    'gemini_gmos': ['GS_HAM_R400_700', 'GS_HAM_R400_860',
                    'GN_HAM_R400_885', 'GN_HAM_NS_B600_620',
                    'GS_HAM_MULTI_R400_700', 'GN_E2V_MULTI_R400_600',
                    'GS_HAM_B600_MOS'],
    'gemini_flamingos2': ['HK_HK', 'JH_JH'],
    'gtc_osiris': ['R1000B', 'R1000BMOS', 'R1000RMOS', 'R2500R', 'R2500V'],
    'gtc_osiris_plus': ['R1000R', 'R300B'],
    'keck_esi': ['Ech_1x1', 'Ech_2x1'],
    'keck_deimos': ['600ZD_M_6500', '600ZD_tilted', '1200G_M_7750', '830G_LVM_8400', '830G_M_8100_26',
                    '830G_M_8500', '830G_L_8100', '1200B_M_5200', '1200G_M_5500',
                    '900ZD_M_6000', '1200B_LVM_5200', '900ZD_LVM_5500',
                    '830G_M_9000_dither'],
    'keck_hires': [
        'HS1700+6416_H45aH_RED_B2_ECH_0.00_XD_-0.00_1x2',  # This one has bad HDUs
        'J0100+2802_H204Hr_RED_C1_ECH_0.75_XD_1.69_1x2',
        'J0100+2802_H204Hr_RED_C1_ECH_-0.82_XD_1.62_1x2',
        'J0100+2802_H237Hr_RED_C1_ECH_0.88_XD_1.46_1x2',
        'J0100+2802_H237Hr_RED_C1_ECH_-0.91_XD_1.46_1x2',
        'J0100+2802_N255Hr_RED_C2_ECH_0.74_XD_1.39_1x3',
        'J0306+1853_U074_RED_C2_ECH_0.72_XD_1.42_1x3',
        'J0306+1853_U074_RED_C2_ECH_-0.86_XD_1.31_1x3',
        'J1723+2243_W241_RED_C5_ECH_0.08_XD_0.90_2x2',
        'J1723+2243_W241_RED_C5_ECH_-0.15_XD_0.90_2x2',
        'Q1009+2956_G10H_BLUE_C5_ECH_-0.00_XD_1.02_1x3',
                   ],
    'keck_kcwi': ['small_bh2_4200', 'medium_bl'],
    'keck_kcrm': ['medium_rm1', 'medium_rh3'],
    'keck_nires': ['ABBA_wstandard', 'ABBA_nostandard', 'ABC_nostandard', 'ABpat_wstandard', 'ABBA_nostandard_faint'],
    'keck_nirspec': ['LOW_NIRSPEC-1'],
    'keck_mosfire': ['Y_long', 'J_multi', 'K_long', 'Y_multi', 'long2pos1_H', 'longslit_3x0.7_H', 'mask1_K_with_continuum', 'mask1_J_with_continuum', 'J2_long'],
    'keck_lris_blue': ['multi_600_4000_d560', 'long_400_3400_d560', 'long_600_4000_d560',
                       'multi_300_5000_d680', 'multi_600_4000_slitmask'],
    'keck_lris_blue_orig': ['long_600_4000_d500', 'multi_1200_3400_d460'],
    'keck_lris_red': ['long_150_7500_d560', 'long_300_5000_d560', 'multi_400_8500_d560', 'long_400_8500_longread',
                      'multi_600_5000_d560', 'long_600_7500_d560', 'long_600_10000_d680', 'mulit_831_8200_d560',
                      'multi_900_5500_d560', 'long_1200_7500_d560', 'multi_1200_9000_d680', 'multi_1200_9000_d680_1x2'],
    'keck_lris_red_orig': ['long_150_7500_d500', 'long_300_5000', 'long_400_8500_d560', 'multi_600_5000_d500',
                           'long_600_7500_d680', 'long_600_10000_d460', 'long_831_8200_d460', 'long_900_5500_d560',
                           'long_1200_7500_d560'],
    'keck_lris_red_mark4': ['long_400_8500_d560', 'long_600_10000_d680', 'multi_600_10000_slitmask'],
    'lbt_luci': ['LUCI-I', 'LUCI-II'],
    'lbt_mods': ['MODS1R_Longslit', 'MODS2R_Longslit'],
    'ldt_deveny': ['DV1', 'DV2', 'DV3', 'DV4', 'DV5', 'DV6', 'DV7', 'DV8', 'DV9'],
    'magellan_fire': ['FIRE_Echelle', 'FIRE_Long'],
    'magellan_mage': ['1x1'],
    'mdm_osmos': ['MDM4K', 'R4K'],
    'mdm_modspec': ['Echelle'],
    'mmt_binospec': ['Longslit_G600', 'Multislit_G270', 'Longslit_G1000'],
    'mmt_mmirs': ['HK_zJ', 'J_zJ', 'K_K'],
    'mmt_bluechannel': ['300l', '500GPM', '800GPM', '832GPM_1st', '832GPM_2nd', '1200GPM'],
    'ntt_efosc2': ['gr4', 'gr5', 'gr6'],
    'not_alfosc': ['grism3', 'grism4', 'grism5', 'grism7', 'grism10', 'grism11', 'grism17', 'grism18', 'grism19', 'grism20', 'grism4_nobin'],
    'p200_dbsp_blue': ['600_4000_d55', '600_4000_d68', '1200_5000_d68'],
    'p200_dbsp_red': ['316_7500_d55', '600_10000_d55', '1200_7100_d68'],
    'p200_tspec': ['TSPEC'],
    'shane_kast_blue': ['452_3306_d57', '600_4310_d55', '830_3460_d46'],
    'shane_kast_red': ['300_7500_Ne', '600_7500_d55_ret', '600_7500_d57', '600_5000_d46', '1200_5000_d57'],
    'soar_goodman_red': ['M1', 'M2', '600red'],
    'soar_goodman_blue': ['M1'],
    'tng_dolores': ['LRB'],
    'vlt_fors2': ['300I', '600Z', '300I_MOS'],
    'vlt_sinfoni': ['K_0.8'],
    'vlt_xshooter': ['VIS_1x1', 'VIS_2x1', 'VIS_2x2', 'VIS_manual', 'NIR', 'UVB_1x1', 'UVB_1x1_Feige110', 'VIS_1x1_Feige110', 'NIR_Feige110', 'VIS_1x1_LTT3218', 'NIR_LTT3218'],
}